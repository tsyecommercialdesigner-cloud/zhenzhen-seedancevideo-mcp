"""Persisted artifact delivery, independent of provider generation and billing."""

import asyncio
import json
import os
import time
import uuid
from pathlib import Path

import pywintypes

from .artifact_files import (
    ArtifactError,
    container,
    copy_async,
    destination,
    fingerprint,
    pinned_directory,
)
from .artifact_manifest import completeness
from .materials import MaterialError
from .network import NetworkError
from .scheduler import stamp
from .storage import StorageError
from .task_state import _change, _load, _public, _version
from .windows_security import SecurityError


class ArtifactService:
    def __init__(
        self, database, configuration, network, *, wall=time.time, hook=lambda point: None
    ):
        self.db, self.config, self.network = database, configuration, network
        self.wall, self.hook = wall, hook
        self.slots = asyncio.Semaphore(configuration.limits["DOWNLOAD_CONCURRENCY"])
        self.work = {}
        self.closed = False

    async def register(self, task_id, references, *, complete=True):
        """Internal correlated adapter contract, never exposed as arbitrary URL tool."""
        if type(complete) is not bool:
            raise ArtifactError("ARTIFACT_MANIFEST_INVALID")
        if not references or not any(ref.get("required", True) for ref in references):
            raise ArtifactError("ARTIFACT_SET_UNVERIFIED")
        if len(references) > 16:
            raise ArtifactError("ARTIFACT_SET_TOO_LARGE")

        def save(c):
            row = _load(c, task_id)
            if row["remote_state"] != "succeeded" or row["auto_mode"] != "active":
                raise ArtifactError("DOWNLOAD_NOT_AUTHORIZED")
            existing = c.execute(
                "SELECT artifact_id FROM artifacts WHERE task_id=?", (task_id,)
            ).fetchall()
            if existing:
                return [item[0] for item in existing]
            ids = []
            for ref in references:
                fmt = ref.get("format", "mp4")
                if fmt not in ("mp4", "mov", "jpg") or not isinstance(ref.get("url"), str):
                    raise ArtifactError("ARTIFACT_CONTRACT_UNVERIFIED")
                identifier = uuid.uuid4().hex
                target = destination(str(Path(row["output_dir"]) / (identifier + "." + fmt)))
                c.execute(
                    "INSERT INTO "
                    "artifacts(artifact_id,task_id,source_url,required,target_path,state) "
                    "VALUES (?,?,?,?,?,'pending')",
                    (identifier, task_id, ref["url"], int(ref.get("required", True)), str(target)),
                )
                self._budget(c, identifier, task_id, row["epoch"], 1)
                ids.append(identifier)
            if not complete:
                reasons = set(json.loads(row["attention"])) | {"ARTIFACT_SET_UNVERIFIED"}
                _change(
                    c,
                    row,
                    {"attention": json.dumps(sorted(reasons))},
                    kind="artifact_set_unverified",
                    now=stamp(self.wall()),
                )
            row = _load(c, task_id)
            c.execute(
                "INSERT INTO task_events(task_id,version,epoch,kind,recorded_at,details) "
                "VALUES (?,?,?,'artifact_manifest_registered',?,?)",
                (
                    task_id,
                    row["version"],
                    row["epoch"],
                    stamp(self.wall()),
                    json.dumps({"complete": complete}),
                ),
            )
            return ids

        return await self.db.execute(save)

    def _budget(self, c, artifact_id, task_id, epoch, number):
        c.execute(
            "INSERT INTO attempts(attempt_id,task_id,phase,round,epoch,state,started_at,"
            "remaining_budget,evidence_digest) VALUES (?,?, "
            "'download_budget',?,?,'finished',?,?,?)",
            (
                str(uuid.uuid4()),
                task_id,
                number,
                epoch,
                stamp(self.wall()),
                self.config.limits["DOWNLOAD_RETRIES"],
                artifact_id,
            ),
        )

    async def _get(self, identifier):
        def read(c):
            item = c.execute(
                "SELECT * FROM artifacts WHERE artifact_id=?", (identifier,)
            ).fetchone()
            if item is None:
                raise ArtifactError("ARTIFACT_NOT_FOUND")
            return dict(item), _load(c, item["task_id"])

        return await self.db.execute(read, write=False)

    def _summarize(self, c, task_id):
        row = _load(c, task_id)
        items = c.execute(
            "SELECT state,required FROM artifacts WHERE task_id=?", (task_id,)
        ).fetchall()
        ready = (
            completeness(c, task_id) and bool(items) and all(a[0] == "ready" for a in items if a[1])
        )
        delivery = (
            "ready" if ready else ("partial" if any(a[0] == "ready" for a in items) else "pending")
        )
        updates = {"delivery": delivery}
        if items and all(a[0] == "ready" for a in items) and row["auto_mode"] == "active":
            updates["attention"] = json.dumps(
                [
                    r
                    for r in json.loads(row["attention"])
                    if not r.startswith("ARTIFACT_") or r == "ARTIFACT_SET_UNVERIFIED"
                ]
            )
        if ready and row["auto_mode"] == "active":
            reasons = [r for r in json.loads(row["attention"]) if not r.startswith("ARTIFACT_")]
            updates.update(stage="settled", cleanup_state="pending", attention=json.dumps(reasons))
        _change(c, row, updates, kind="artifact_delivery", now=stamp(self.wall()))

    async def download(self, identifier):
        if self.closed:
            raise ArtifactError("DOWNLOAD_SERVICE_CLOSED")
        if identifier not in self.work:
            operation = asyncio.create_task(self._download(identifier))
            self.work[identifier] = operation

            def finished(done):
                if self.work.get(identifier) is done:
                    self.work.pop(identifier, None)
                if not done.cancelled():
                    done.exception()

            operation.add_done_callback(finished)
        return await asyncio.shield(self.work[identifier])

    async def _download(self, identifier):
        async with self.slots:
            artifact, task = await self._get(identifier)
            if artifact["state"] != "pending" or task["auto_mode"] != "active":
                return
            target = Path(artifact["target_path"])
            temporary = target.with_name(
                "." + identifier + ".download-" + uuid.uuid4().hex + ".tmp"
            )
            attempt = str(uuid.uuid4())

            def begin(c):
                current = _load(c, task["task_id"])
                if current["epoch"] != task["epoch"] or current["auto_mode"] != "active":
                    raise ArtifactError("DOWNLOAD_NOT_AUTHORIZED")
                budget = c.execute(
                    "SELECT * FROM attempts WHERE phase='download_budget' "
                    "AND evidence_digest=? "
                    "ORDER BY round DESC LIMIT 1",
                    (identifier,),
                ).fetchone()
                if budget["next_attempt_at"] and budget["next_attempt_at"] > stamp(self.wall()):
                    return None
                c.execute(
                    "UPDATE artifacts SET state='downloading',temporary_path=? WHERE artifact_id=?",
                    (str(temporary), identifier),
                )
                c.execute(
                    "INSERT INTO attempts(attempt_id,task_id,phase,round,epoch,state,started_at,"
                    "remaining_budget,evidence_digest) VALUES "
                    "(?,?,'artifact_transfer',?,?,'intent',?,0,?)",
                    (
                        attempt,
                        task["task_id"],
                        budget["round"],
                        task["epoch"],
                        stamp(self.wall()),
                        json.dumps({"artifact_id": identifier}),
                    ),
                )
                return dict(budget)

            budget = await self.db.execute(begin)
            if budget is None:
                return
            publish_saved = False
            try:
                with pinned_directory(target.parent):

                    async def transfer():
                        async with self.network.stream(
                            "GET", artifact["source_url"], phase="download"
                        ) as response:
                            if response.status_code in (401, 403, 404, 410):
                                raise ArtifactError("ARTIFACT_LINK_REFRESH_UNVERIFIED")
                            if response.status_code != 200:
                                raise NetworkError("DOWNLOAD_HTTP_FAILURE")
                            if response.headers.get("content-encoding", "identity") != "identity":
                                raise ArtifactError("ARTIFACT_ENCODING_UNSUPPORTED")
                            length = response.headers.get("content-length")
                            if length is not None and (not length.isdecimal() or int(length) <= 0):
                                raise ArtifactError("ARTIFACT_INVALID_LENGTH")
                            limit = self.config.limits["DOWNLOAD_BYTES_LIMIT"]
                            size = 0
                            with temporary.open("xb") as stream:
                                async for chunk in response.aiter_bytes():
                                    size += len(chunk)
                                    if limit is not None and size > limit:
                                        raise ArtifactError("ARTIFACT_BYTES_LIMIT")
                                    # Finish bounded writes before cancellation closes the handle.
                                    await self._file_call(stream.write, chunk)
                                await self._file_call(stream.flush)
                                await self._file_call(os.fsync, stream.fileno())
                            if not size or (length is not None and size != int(length)):
                                raise ArtifactError("ARTIFACT_LENGTH_MISMATCH")

                    await self.db.run_effect(attempt, transfer)
                    fmt = await self._file_call(container, temporary)
                    if fmt != target.suffix[1:]:
                        raise ArtifactError("ARTIFACT_FORMAT_MISMATCH")
                    proof = await self._file_call(fingerprint, temporary)
                    proof["artifact_id"] = identifier
                    proof["overwrite"] = budget["remote_id"] == "overwrite"

                    def intent(c):
                        current = _load(c, task["task_id"])
                        if current["epoch"] != task["epoch"] or current["auto_mode"] != "active":
                            raise ArtifactError("DOWNLOAD_NOT_AUTHORIZED")
                        c.execute(
                            "UPDATE attempts SET "
                            "phase='artifact_publish',effect_started=0,evidence_digest=? "
                            "WHERE attempt_id=?",
                            (json.dumps(proof), attempt),
                        )
                        c.execute(
                            "UPDATE artifacts SET state='publishing',sha256=?,size_bytes=? WHERE "
                            "artifact_id=?",
                            (proof["sha256"], proof["size_bytes"], identifier),
                        )

                    await self.db.execute(intent)
                    publish_saved = True
                    self.hook("download_before_publish")

                    async def publish():
                        (os.replace if proof["overwrite"] else os.rename)(temporary, target)

                    await self.db.run_effect(attempt, publish)
                    self.hook("download_after_publish")
                    await self._ready(identifier, attempt)
            except StorageError:
                raise  # Intent is retained; recovery must inspect the actual file.
            except asyncio.CancelledError:
                raise  # Interrupted transfer/publish reconciled on restart.
            except (
                ArtifactError,
                NetworkError,
                OSError,
                MaterialError,
                SecurityError,
                pywintypes.error,
            ) as error:
                if publish_saved:
                    raise  # Preserve proof and files until recovery.
                temporary.unlink(missing_ok=True)
                await self._failure(artifact, task, attempt, budget, error)

    @staticmethod
    async def _file_call(function, *args):
        work = asyncio.create_task(asyncio.to_thread(function, *args))
        try:
            return await asyncio.shield(work)
        except asyncio.CancelledError:
            await asyncio.gather(work, return_exceptions=True)
            raise

    async def _ready(self, identifier, attempt):
        def save(c):
            row = c.execute(
                "SELECT task_id FROM artifacts WHERE artifact_id=?", (identifier,)
            ).fetchone()
            c.execute(
                "UPDATE artifacts SET state='ready',temporary_path=NULL WHERE artifact_id=?",
                (identifier,),
            )
            c.execute(
                "UPDATE attempts SET state='finished',finished_at=? WHERE attempt_id=?",
                (stamp(self.wall()), attempt),
            )
            self._summarize(c, row[0])

        await self.db.execute(save)

    async def _failure(self, artifact, task, attempt, budget, error):
        def save(c):
            row = _load(c, task["task_id"])
            retry = isinstance(error, NetworkError) and budget["remaining_budget"] > 0
            state = "pending" if retry else "attention"
            reason = (
                "ARTIFACT_RETRIES_EXHAUSTED"
                if isinstance(error, NetworkError)
                else str(error)
                if isinstance(error, ArtifactError)
                else "ARTIFACT_STORAGE_ERROR"
            )
            c.execute(
                "UPDATE artifacts SET state=?,temporary_path=NULL WHERE artifact_id=?",
                (state, artifact["artifact_id"]),
            )
            c.execute("UPDATE attempts SET state='finished' WHERE attempt_id=?", (attempt,))
            if retry:
                remaining = budget["remaining_budget"] - 1
                delay = min(60, 2 ** min(6, self.config.limits["DOWNLOAD_RETRIES"] - remaining))
                c.execute(
                    "UPDATE attempts SET remaining_budget=?,next_attempt_at=? WHERE attempt_id=?",
                    (remaining, stamp(self.wall() + delay), budget["attempt_id"]),
                )
            else:
                reasons = set(json.loads(row["attention"])) | {reason}
                _change(
                    c,
                    row,
                    {"attention": json.dumps(sorted(reasons))},
                    kind="artifact_failure",
                    now=stamp(self.wall()),
                )
            self._summarize(c, task["task_id"])

        await self.db.execute(save)

    async def due(self):
        ids = await self.db.execute(
            lambda c: [
                r[0]
                for r in c.execute(
                    "SELECT artifact_id FROM artifacts a JOIN tasks t ON a.task_id=t.task_id "
                    "WHERE a.state='pending' AND t.auto_mode='active'"
                )
            ],
            write=False,
        )
        await asyncio.gather(*(self.download(identifier) for identifier in ids))

    async def recover(self):
        intents = await self.db.execute(
            lambda c: [
                dict(r)
                for r in c.execute(
                    "SELECT * FROM attempts WHERE state='intent' AND phase IN "
                    "('artifact_transfer','artifact_publish')"
                )
            ],
            write=False,
        )
        for attempt in intents:
            proof = json.loads(attempt["evidence_digest"])
            artifact, task = await self._get(proof["artifact_id"])
            target, temp = Path(artifact["target_path"]), Path(artifact["temporary_path"])
            with pinned_directory(target.parent):
                if attempt["phase"] == "artifact_publish" and await self._file_call(target.exists):
                    try:
                        actual = await self._file_call(fingerprint, target)
                    except (OSError, MaterialError, SecurityError):
                        actual = None
                    if actual and all(actual[k] == proof[k] for k in actual):
                        await self._ready(artifact["artifact_id"], attempt["attempt_id"])
                        continue
                # Never publish interrupted work during recovery, nor overwrite a stranger.
                await self._file_call(lambda temp=temp: temp.unlink(missing_ok=True))

                exists = await self._file_call(target.exists)

                def reset(c, artifact=artifact, attempt=attempt, task=task, exists=exists):
                    budget = c.execute(
                        "SELECT * FROM attempts WHERE phase='download_budget' "
                        "AND evidence_digest=? "
                        "ORDER BY round DESC LIMIT 1",
                        (artifact["artifact_id"],),
                    ).fetchone()
                    state = "attention" if exists or budget["remaining_budget"] == 0 else "pending"
                    if state == "pending":
                        c.execute(
                            "UPDATE attempts SET remaining_budget=remaining_budget-1 "
                            "WHERE attempt_id=?",
                            (budget["attempt_id"],),
                        )
                    c.execute(
                        "UPDATE artifacts SET state=?,temporary_path=NULL WHERE artifact_id=?",
                        (state, artifact["artifact_id"]),
                    )
                    c.execute(
                        "UPDATE attempts SET state='reconciled' WHERE attempt_id=?",
                        (attempt["attempt_id"],),
                    )
                    if state == "attention":
                        row = _load(c, task["task_id"])
                        _change(
                            c,
                            row,
                            {
                                "attention": json.dumps(
                                    sorted(
                                        set(json.loads(row["attention"]))
                                        | {
                                            "ARTIFACT_TARGET_CONFLICT"
                                            if exists
                                            else "ARTIFACT_RETRIES_EXHAUSTED"
                                        }
                                    )
                                )
                            },
                            kind="artifact_recovery",
                            now=stamp(self.wall()),
                        )

                await self.db.execute(reset)

    async def verify(self, identifier, *, digest=True):
        artifact, task = await self._get(identifier)
        if artifact["state"] not in ("ready", "missing", "changed"):
            return self._public(artifact)
        target = Path(artifact["target_path"])
        try:
            actual = (
                await self._file_call(fingerprint, target)
                if digest
                else {"size_bytes": (await self._file_call(target.stat)).st_size}
            )
            state = (
                "ready"
                if all(actual[k] == artifact[k] for k in ("sha256", "size_bytes") if k in actual)
                else "changed"
            )
        except (OSError, RuntimeError):
            state = "missing" if not await self._file_call(target.exists) else "changed"
        if state != artifact["state"]:

            def save(c):
                c.execute("UPDATE artifacts SET state=? WHERE artifact_id=?", (state, identifier))
                row = _load(c, task["task_id"])
                reasons = set(json.loads(row["attention"])) | {"ARTIFACT_EXTERNAL_CHANGE"}
                _change(
                    c,
                    row,
                    {
                        "delivery": state if state != "ready" else "partial",
                        "attention": json.dumps(sorted(reasons)),
                    },
                    kind="artifact_external_change",
                    now=stamp(self.wall()),
                )

            await self.db.execute(save)
            artifact["state"] = state
        return self._public(artifact)

    @staticmethod
    def _public(artifact):
        return {
            k: artifact[k]
            for k in (
                "artifact_id",
                "task_id",
                "target_path",
                "required",
                "state",
                "size_bytes",
                "sha256",
            )
        }

    async def list(self, task_id, *, after="", limit=20):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ArtifactError("INVALID_PAGE_SIZE")
        ids = await self.db.execute(
            lambda c: [
                r[0]
                for r in c.execute(
                    "SELECT artifact_id FROM artifacts WHERE task_id=? AND artifact_id>? "
                    "ORDER BY artifact_id LIMIT ?",
                    (task_id, after, limit + 1),
                )
            ],
            write=False,
        )
        return {
            "items": [await self.verify(identifier, digest=False) for identifier in ids[:limit]],
            "next_cursor": ids[limit - 1] if len(ids) > limit else None,
        }

    async def retry(self, task_id, *, expected_version, overwrite=False):
        if type(overwrite) is not bool:
            raise ArtifactError("INVALID_OVERWRITE")
        # Explicit recovery must not erase a still-existing externally modified file.
        items = await self.db.execute(
            lambda c: [
                dict(r) for r in c.execute("SELECT * FROM artifacts WHERE task_id=?", (task_id,))
            ],
            write=False,
        )
        if not items:
            raise ArtifactError("ARTIFACT_LINK_REFRESH_UNVERIFIED")
        if any(
            item["artifact_id"] in self.work and not self.work[item["artifact_id"]].done()
            for item in items
        ):
            raise ArtifactError("ARTIFACT_OPERATION_IN_PROGRESS")
        if not overwrite and await self._file_call(
            lambda: any(
                item["state"] != "ready" and Path(item["target_path"]).exists() for item in items
            )
        ):
            raise ArtifactError("ARTIFACT_TARGET_EXISTS")

        def save(c):
            row = _load(c, task_id)
            if row["auto_mode"] == "active" and all(
                item["state"] in ("pending", "ready") for item in items
            ):
                return _public(row)
            _version(row, expected_version)
            if row["remote_state"] != "succeeded":
                raise ArtifactError("DOWNLOAD_NOT_AUTHORIZED")
            for item in items:
                if item["state"] == "ready":
                    continue
                latest = (
                    c.execute(
                        "SELECT max(round) FROM attempts WHERE phase='download_budget' AND "
                        "evidence_digest=?",
                        (item["artifact_id"],),
                    ).fetchone()[0]
                    or 0
                )
                self._budget(c, item["artifact_id"], task_id, row["epoch"] + 1, latest + 1)
                if overwrite:
                    c.execute(
                        "UPDATE attempts SET remote_id='overwrite' WHERE phase='download_budget' "
                        "AND evidence_digest=? AND round=?",
                        (item["artifact_id"], latest + 1),
                    )
                c.execute(
                    "UPDATE artifacts SET state='pending' WHERE artifact_id=?",
                    (item["artifact_id"],),
                )
            return _change(
                c,
                row,
                {
                    "epoch": row["epoch"] + 1,
                    "auto_mode": "active",
                    "stage": "downloading",
                    "cleanup_state": "none",
                },
                kind="artifact_retry",
                now=stamp(self.wall()),
            )

        return await self.db.execute(save)

    async def copy(
        self,
        identifier,
        target_path,
        *,
        workspace_root=None,
        overwrite=False,
        hook=lambda point: None,
    ):
        if type(overwrite) is not bool:
            raise ArtifactError("INVALID_OVERWRITE")
        item = await self.verify(identifier)
        if item["state"] != "ready":
            raise ArtifactError("ARTIFACT_NOT_READY")
        target = destination(target_path, workspace_root)
        source = Path(item["target_path"])
        other = await self.db.execute(
            lambda c: c.execute(
                "SELECT artifact_id FROM artifacts WHERE target_path=? COLLATE NOCASE",
                (str(target),),
            ).fetchone(),
            write=False,
        )
        if other and other[0] != identifier:
            raise ArtifactError("SERVICE_ARTIFACT_OVERWRITE_FORBIDDEN")
        return await copy_async(source, target, item, overwrite=overwrite, hook=hook)

    async def close(self):
        self.closed = True
        tasks = list(self.work.values())
        if tasks:
            _, pending = await asyncio.wait(
                tasks, timeout=self.config.limits["SHUTDOWN_DRAIN_SECONDS"]
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
