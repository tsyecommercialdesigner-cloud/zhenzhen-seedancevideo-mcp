"""Backend-owned intake transactions, replay identity and user consent."""

import asyncio
import copy
import hashlib
import json
import os
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .draft_evidence import local_draft_fact
from .material_readers import material_readers
from .materials import owned_path, receive
from .models import get_model
from .parameters import MediaFact, normalize
from .task_state import _load, _public, _version
from .windows_security import protect_directory


class AdmissionError(RuntimeError):
    pass


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def now():
    return datetime.now(UTC).isoformat()


def preference(c):
    row = c.execute("SELECT * FROM preferences WHERE name='enhance_prompt'").fetchone()
    return (
        {"enabled": bool(json.loads(row["value"])), "version": row["version"]}
        if row
        else {
            "enabled": False,
            "version": 0,
        }
    )


def authorize(request, policy, once, kind):
    explicit = request.get("enhance_prompt")
    if explicit is not None and type(explicit) is not bool:
        raise AdmissionError("INVALID_ENHANCE_PROMPT")
    if kind in ("upscale", "draft-to-video"):
        if explicit is True:
            raise AdmissionError("ENHANCE_PROMPT_NOT_APPLICABLE")
        return {"enabled": False, "source": "not_applicable", "policy_version": policy["version"]}
    enabled = explicit if explicit is not None else bool(once or policy["enabled"])
    if enabled and not (once or policy["enabled"]):
        raise AdmissionError("PROMPT_AUTHORIZATION_REQUIRED")
    return {
        "enabled": enabled,
        "source": "single_explicit_false"
        if explicit is False
        else (
            "single_allow" if enabled and once else "always_allow" if enabled else "default_false"
        ),
        "policy_version": policy["version"],
    }


def local_inputs(request):
    """Only media URL positions accept {local_path: absolute_path}."""
    result = copy.deepcopy(request)
    inputs = []

    def visit(container, key, slot):
        value = container[key]
        if isinstance(value, dict) and set(value) == {"local_path"}:
            ordinal = len(inputs)
            placeholder = f"https://managed.invalid/input/{ordinal}"
            inputs.append({"source": value["local_path"], "placeholder": placeholder, "slot": slot})
            container[key] = placeholder

    if isinstance(result.get("images"), list):
        for i in range(len(result["images"])):
            visit(result["images"], i, ("images", i))
    metadata = result.get("metadata", {})
    if isinstance(metadata, dict) and isinstance(metadata.get("content"), list):
        for index, item in enumerate(metadata["content"]):
            if isinstance(item, dict):
                kind = item.get("type")
                if kind in ("image_url", "video_url", "audio_url"):
                    nested = item.get(kind)
                    if isinstance(nested, dict) and "url" in nested:
                        visit(nested, "url", ("metadata", "content", index, kind, "url"))
    return result, inputs


def replace_values(value, mapping, path=()):
    if path in mapping:
        return mapping[path]
    if isinstance(value, list):
        return [replace_values(item, mapping, (*path, i)) for i, item in enumerate(value)]
    if isinstance(value, dict):
        return {key: replace_values(item, mapping, (*path, key)) for key, item in value.items()}
    return value


class AdmissionService:
    def __init__(self, database, configuration, connection_binding):
        self.db = database
        self.readers = material_readers(database)
        self.config = configuration
        self.binding = connection_binding
        self.root = configuration.root / "materials"
        protect_directory(self.root)
        self._inflight = {}
        self._semaphore = asyncio.Semaphore(configuration.limits["ADMISSION_CONCURRENCY"])
        self._stop = threading.Event()
        self._repairs = {}

    async def get_preference(self):
        return await self.db.execute(preference, write=False)

    async def draft_fact(self, request):
        return await self.db.execute(
            lambda c: local_draft_fact(c, request, self.binding), write=False
        )

    async def set_preference(self, *, enabled, expected_version, confirmed=False):
        if type(enabled) is not bool or confirmed is not True:
            raise AdmissionError("EXPLICIT_AUTHORIZATION_REQUIRED")

        def change(c):
            old = preference(c)
            if old["enabled"] == enabled:
                return old
            if type(expected_version) is not int or old["version"] != expected_version:
                raise AdmissionError("VERSION_CONFLICT")
            c.execute(
                """INSERT INTO preferences VALUES ('enhance_prompt',?,?,?, ?,?)
                       ON CONFLICT(name) DO UPDATE SET value=excluded.value,
                       version=excluded.version, source=excluded.source,
                       updated_at=excluded.updated_at, revoked_at=excluded.revoked_at""",
                (
                    encoded(enabled),
                    old["version"] + 1,
                    "agent_user_declaration",
                    now(),
                    None if enabled else now(),
                ),
            )
            return preference(c)

        return await self.db.execute(change)

    async def _existing(self, key):
        def read(c):
            row = c.execute("SELECT * FROM tasks WHERE request_key=?", (key,)).fetchone()
            if row is None:
                return None
            event = c.execute(
                "SELECT details FROM task_events WHERE task_id=? AND kind='accepted'",
                (row["task_id"],),
            ).fetchone()
            if event is None:
                raise AdmissionError("ADMISSION_SNAPSHOT_UNAVAILABLE")
            return dict(row), json.loads(event[0])

        return await self.db.execute(read, write=False)

    @staticmethod
    def _response(row, details):
        return _public(row) | {
            "accepted": True,
            "request_key": row["request_key"],
            "authorization": details["authorization"],
            "unverified": details["unverified"],
            "output_dir": row["output_dir"],
            "materials": details.get("materials", []),
        }

    async def find(self, request_key):
        existing = await self._existing(request_key)
        if existing:
            return self._response(*existing)
        receiving = await self.db.execute(
            lambda c: (
                c.execute("SELECT 1 FROM admissions WHERE request_key=?", (request_key,)).fetchone()
                is not None
            ),
            write=False,
        )
        return {
            "accepted": False,
            "request_key": request_key,
            "status": "receiving" if receiving else "not_found",
        }

    async def submit(self, request_key, request, *, api_id="seedance-video", allow_once=False):
        if not isinstance(request_key, str) or not 1 <= len(request_key) <= 128:
            raise AdmissionError("INVALID_REQUEST_KEY")
        if type(allow_once) is not bool or not isinstance(request, dict):
            raise AdmissionError("INVALID_ADMISSION_REQUEST")
        # Snapshot caller-owned objects before yielding; the task owns all subsequent work.
        request = json.loads(encoded(request))
        if self._stop.is_set():
            raise AdmissionError("ADMISSION_STOPPED")
        operation = self._inflight.get(request_key)
        if operation is not None:
            await asyncio.shield(operation)
            return await self._replay(request_key, request, api_id)
        operation = asyncio.create_task(self._submit(request_key, request, api_id, allow_once))
        self._inflight[request_key] = operation

        def finished(task):
            self._inflight.pop(request_key, None)
            if not task.cancelled():
                task.exception()  # Observe failures even when every waiting Host disconnected.

        operation.add_done_callback(finished)
        return await asyncio.shield(operation)

    async def _material_identity(self, request, *, destinations=None):
        prepared, inputs = local_inputs(request)
        mapping, records = {}, []
        remaining = self.config.limits["INPUT_BYTES_LIMIT"]
        for ordinal, item in enumerate(inputs):
            if self.db.storage_fault:
                raise AdmissionError("STORAGE_FAULT")
            destination = owned_path(self.root, destinations[ordinal]) if destinations else None
            record = await asyncio.to_thread(
                receive, item["source"], limit=remaining, destination=destination, stop=self._stop
            )
            record["suffix"] = Path(item["source"]).suffix.lower()
            remaining -= record["size_bytes"]
            # Structured identity distinguishes a local input from a caller URL with identical text.
            mapping[tuple(item["slot"])] = {
                "local_sha256": record["sha256"],
                "size_bytes": record["size_bytes"],
            }
            records.append(record)
        return prepared, replace_values(prepared, mapping), records

    async def _replay(self, key, request, api_id):
        row, details = await self._existing(key)
        async with self._semaphore:
            prepared, identity, records = await self._material_identity(request)
        if api_id != row["api_id"]:
            raise AdmissionError("REQUEST_KEY_CONFLICT")
        if identity != details["explicit_identity"]:
            # Compare equivalent explicit defaults using the original accepted defaults.
            old = details["effective_identity"]
            if "enhance_prompt" in old:
                prepared.setdefault("enhance_prompt", old["enhance_prompt"])
            metadata = prepared.setdefault("metadata", {})
            for name in ("generate_audio", "draft"):
                if name in old.get("metadata", {}):
                    metadata.setdefault(name, old["metadata"][name])
            candidate = normalize(prepared, api_id=api_id).payload()
            _, inputs = local_inputs(request)
            candidate = replace_values(
                candidate,
                {
                    tuple(item["slot"]): {
                        "local_sha256": records[i]["sha256"],
                        "size_bytes": records[i]["size_bytes"],
                    }
                    for i, item in enumerate(inputs)
                },
            )
            if candidate != old:
                raise AdmissionError("REQUEST_KEY_CONFLICT")
        return self._response(row, details)

    async def _submit(self, key, request, api_id, once):
        if await self._existing(key):
            return await self._replay(key, request, api_id)
        prepared, inputs = local_inputs(request)
        model = get_model(prepared.get("model"), api_id=api_id)
        normalize(prepared, api_id=api_id)
        authorize(request, await self.get_preference(), once, model.kind)
        operation_id = uuid.uuid4().hex
        names = [uuid.uuid4().hex + ".input" for _ in inputs]

        def reserve(c):
            if c.execute(
                "SELECT 1 FROM preferences WHERE name IN (?,?,?) AND value='true'",
                ("dispatch:all", "dispatch:" + api_id, "dispatch:model:" + model.model_id),
            ).fetchone():
                raise AdmissionError("API_PROTECTED")
            count = c.execute("""SELECT count(*) FROM tasks WHERE stage IN ('queued','preparing')
                AND locally_cancelled=0 AND auto_mode!='abandoned'""").fetchone()[0]
            count += c.execute("SELECT count(*) FROM admissions").fetchone()[0]
            if count >= self.config.limits["QUEUE_LIMIT"]:
                raise AdmissionError("QUEUE_FULL")
            c.execute(
                "INSERT INTO admissions VALUES (?,?,?,?,?,?)",
                (
                    key,
                    operation_id,
                    hashlib.sha256(encoded(prepared).encode()).hexdigest(),
                    self.config.limits["INPUT_BYTES_LIMIT"],
                    encoded(names),
                    now(),
                ),
            )

        await self.db.execute(reserve)
        try:
            async with self._semaphore:
                prepared, identity, records = await self._material_identity(
                    request, destinations=names
                )

                def accept(c):
                    authorization = authorize(request, preference(c), once, model.kind)
                    if model.kind not in ("draft-to-video", "upscale"):
                        prepared["enhance_prompt"] = authorization["enabled"]
                    snapshot = normalize(
                        prepared,
                        api_id=api_id,
                        draft_fact=local_draft_fact(c, prepared, self.binding),
                        media_facts={
                            item["placeholder"]: MediaFact(size_bytes=records[i]["size_bytes"])
                            for i, item in enumerate(inputs)
                        },
                    )
                    task_id = uuid.uuid4().hex
                    payload = replace_values(
                        snapshot.payload(),
                        {
                            tuple(item["slot"]): {"material_id": names[i][:-6]}
                            for i, item in enumerate(inputs)
                        },
                    )
                    details = {
                        "provider_execution_authorized": self.config.execution_mode == "provider",
                        "explicit_identity": identity,
                        "effective_identity": replace_values(
                            snapshot.payload(),
                            {
                                tuple(item["slot"]): {
                                    "local_sha256": records[i]["sha256"],
                                    "size_bytes": records[i]["size_bytes"],
                                }
                                for i, item in enumerate(inputs)
                            },
                        ),
                        "authorization": authorization,
                        "unverified": list(snapshot.unresolved),
                        "rule_version": snapshot.rule_version,
                        "materials": [
                            {"material_id": names[i][:-6], **record}
                            for i, record in enumerate(records)
                        ],
                    }
                    c.execute(
                        """INSERT INTO tasks(task_id,request_key,api_id,model,kind,rule_version,
                        intent_digest,effective_parameters,output_dir,connection_binding,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            task_id,
                            key,
                            api_id,
                            model.model_id,
                            model.kind,
                            snapshot.rule_version,
                            hashlib.sha256(encoded(identity).encode()).hexdigest(),
                            encoded(payload),
                            str(self.config.output_dir),
                            self.binding,
                            now(),
                        ),
                    )
                    for i, record in enumerate(records):
                        c.execute(
                            "INSERT INTO material_copies VALUES (?,?,?,?,?,'ready',?)",
                            (
                                names[i][:-6],
                                task_id,
                                str(self.root / names[i]),
                                record["sha256"],
                                record["size_bytes"],
                                i,
                            ),
                        )
                    c.execute(
                        """INSERT INTO task_events(task_id,version,epoch,kind,recorded_at,details)
                                 VALUES (?,1,0,'accepted',?,?)""",
                        (task_id, now(), encoded(details)),
                    )
                    c.execute("DELETE FROM admissions WHERE operation_id=?", (operation_id,))
                    row = c.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
                    return self._response(dict(row), details)

                return await self.db.execute(accept)
        except Exception:
            # Never delete on an uncertain commit. Startup reconciliation owns that case.
            if not self.db.storage_fault and not await self._existing(key):
                for name in names:
                    owned_path(self.root, name).unlink(missing_ok=True)
                await self.db.execute(
                    lambda c: (
                        c.execute(
                            "DELETE FROM admissions WHERE operation_id=?", (operation_id,)
                        ).rowcount
                    )
                )
            raise

    async def recover(self):
        """Call under exclusive backend ownership, before accepting any client."""
        repairs = await self.db.execute(
            lambda c: [
                json.loads(r[0])
                for r in c.execute(
                    "SELECT details FROM task_events WHERE kind='material_repair_intent'"
                )
            ],
            write=False,
        )
        for repair in repairs:
            if self.db.storage_fault:
                raise AdmissionError("STORAGE_FAULT")
            owned_path(self.root, repair["temporary_name"]).unlink(missing_ok=True)
        rows = await self.db.execute(
            lambda c: [dict(r) for r in c.execute("SELECT * FROM admissions")], write=False
        )
        for row in rows:
            if not await self._existing(row["request_key"]):
                for name in json.loads(row["temporary_materials"]):
                    if self.db.storage_fault:
                        raise AdmissionError("STORAGE_FAULT")
                    owned_path(self.root, name).unlink(missing_ok=True)
            await self.db.execute(
                lambda c, key=row["request_key"]: (
                    c.execute("DELETE FROM admissions WHERE request_key=?", (key,)).rowcount
                )
            )

    async def repair(self, task_id, material_id, source, *, expected_version):
        if self._stop.is_set():
            raise AdmissionError("ADMISSION_STOPPED")
        if task_id in self._repairs:
            raise AdmissionError("MATERIAL_REPAIR_IN_PROGRESS")
        task = asyncio.create_task(
            self._guarded_repair(task_id, material_id, source, expected_version)
        )
        self._repairs[task_id] = task

        def finished(done):
            self._repairs.pop(task_id, None)
            if not done.cancelled():
                done.exception()

        task.add_done_callback(finished)
        return await asyncio.shield(task)

    async def _guarded_repair(self, task_id, material_id, source, expected_version):
        async with self.readers.use(task_id) as stop:
            return await self._repair(task_id, material_id, source, expected_version, stop)

    async def _repair(self, task_id, material_id, source, expected_version, stop):
        name = uuid.uuid4().hex + ".input"
        attempt = uuid.uuid4().hex

        def reserve(c):
            row = _load(c, task_id)
            _version(row, expected_version)
            if (
                row["remote_state"] != "not_submitted"
                or row["stage"] not in ("queued", "preparing")
                or row["locally_cancelled"]
                or row["auto_mode"] == "abandoned"
            ):
                raise AdmissionError("MATERIAL_REPAIR_NOT_ALLOWED")
            material = c.execute(
                "SELECT * FROM material_copies WHERE task_id=? AND material_id=?",
                (task_id, material_id),
            ).fetchone()
            if material is None:
                raise AdmissionError("MATERIAL_NOT_FOUND")
            # A prior interrupted repair remains blocked until this explicit repair.
            c.execute(
                "UPDATE material_copies SET state='repairing' WHERE material_id=?", (material_id,)
            )
            c.execute(
                """INSERT INTO attempts(attempt_id,task_id,phase,round,epoch,state,
                         started_at,remaining_budget)
                         VALUES (?,?,'material_repair',0,?,'intent',?,0)""",
                (attempt, task_id, row["epoch"], now()),
            )
            c.execute(
                """INSERT INTO task_events(task_id,version,epoch,kind,recorded_at,details)
                         VALUES (?,?,?,'material_repair_intent',?,?)""",
                (
                    task_id,
                    row["version"],
                    row["epoch"],
                    now(),
                    encoded({"temporary_name": name, "material_id": material_id}),
                ),
            )
            return dict(material)

        material = await self.db.execute(reserve)
        destination = owned_path(self.root, name)
        try:
            async with self._semaphore:
                if self.db.storage_fault:
                    raise AdmissionError("STORAGE_FAULT")
                actual = await self.readers.thread(
                    receive,
                    source,
                    limit=material["size_bytes"],
                    destination=destination,
                    stop=stop,
                )
                if (
                    actual["sha256"] != material["sha256"]
                    or actual["size_bytes"] != material["size_bytes"]
                ):
                    raise AdmissionError("MATERIAL_CONTENT_CONFLICT")
                # The task's submission gate rejects non-ready material until reconciliation.
                target = owned_path(self.root, material_id + ".input")
                if str(target) != material["managed_path"]:
                    raise AdmissionError("MATERIAL_OWNERSHIP_INVALID")
                await self.db.execute(
                    lambda c: (
                        c.execute(
                            "UPDATE attempts SET effect_started=1 WHERE attempt_id=?", (attempt,)
                        ).rowcount
                    )
                )
                if self.db.storage_fault:
                    raise AdmissionError("STORAGE_FAULT")
                os.replace(destination, target)

                def finish(c):
                    row = _load(c, task_id)
                    c.execute(
                        "UPDATE material_copies SET state='ready' WHERE material_id=?",
                        (material_id,),
                    )
                    c.execute(
                        """UPDATE attempts SET state='reconciled',finished_at=? WHERE task_id=?
                                 AND phase='material_repair' AND state='intent'""",
                        (now(), task_id),
                    )
                    c.execute("UPDATE tasks SET version=version+1 WHERE task_id=?", (task_id,))
                    c.execute(
                        """INSERT INTO task_events(task_id,version,epoch,kind,recorded_at,details)
                                 VALUES (?,?,?,'material_repaired',?,'{}')""",
                        (task_id, row["version"] + 1, row["epoch"], now()),
                    )
                    return _public(_load(c, task_id))

                return await self.db.execute(finish)
        finally:
            if not self.db.storage_fault:
                destination.unlink(missing_ok=True)

    async def close(self):
        self._stop.set()
        await asyncio.gather(
            *list(self._inflight.values()), *list(self._repairs.values()), return_exceptions=True
        )
