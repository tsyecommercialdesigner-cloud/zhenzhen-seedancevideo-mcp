"""Durable, bounded material preparation; never submits generation requests."""

import asyncio
import json
import random
import time
import uuid
from datetime import UTC, datetime

from .material_readers import material_readers
from .materials import MaterialError, locked_source, owned_path
from .network import NetworkError
from .provider import ProviderFailure
from .task_state import StateError, _change, _load
from .uploads import UploadError, upload_once


def stamp(value):
    return datetime.fromtimestamp(value, UTC).isoformat()


def at(value):
    return datetime.fromisoformat(value).timestamp() if value else None


class UploadService:
    def __init__(
        self, database, configuration, binding, network, *, send=upload_once, wall=time.time
    ):
        self.db, self.config, self.binding = database, configuration, binding
        self.network, self.send, self.wall = network, send, wall
        self.readers = material_readers(database)
        self.locks = {}

    def _eligible(self, c, task_id, epoch):
        row = _load(c, task_id)
        if (
            row["epoch"] != epoch
            or row["auto_mode"] != "active"
            or row["locally_cancelled"]
            or row["remote_state"] != "not_submitted"
            or row["stage"] not in ("queued", "preparing")
            or row["connection_binding"] != self.binding
        ):
            raise StateError("UPLOAD_NOT_ALLOWED")
        return row

    def _attention(self, c, row, code):
        _change(
            c,
            row,
            {
                "auto_mode": "needs_attention",
                "attention": json.dumps(sorted(set(json.loads(row["attention"])) | {code})),
            },
            kind="upload_attention",
            now=stamp(self.wall()),
        )

    async def recover(self):
        def reconcile(c):
            for a in c.execute(
                "SELECT * FROM attempts WHERE phase LIKE 'upload:%' AND state='intent'"
            ).fetchall():
                uid = a["evidence_digest"]
                c.execute(
                    "UPDATE attempts SET state='reconciled',finished_at=? WHERE attempt_id=?",
                    (stamp(self.wall()), a["attempt_id"]),
                )
                c.execute(
                    "UPDATE uploads SET state='pending' WHERE upload_id=? AND state='uploading'",
                    (uid,),
                )

        await self.db.execute(reconcile)

    def guard(self, c, task_id):
        """Runs inside the same transaction as the generation intent."""
        for m in c.execute("SELECT * FROM material_copies WHERE task_id=?", (task_id,)):
            u = c.execute(
                "SELECT * FROM uploads WHERE material_id=? AND connection_binding=?",
                (m["material_id"], self.binding),
            ).fetchone()
            if (
                not u
                or u["state"] != "ready"
                or not u["expires_at"]
                or at(u["expires_at"]) <= self.wall()
            ):
                raise StateError("UPLOAD_REFERENCE_NOT_READY")
            latest = c.execute(
                "SELECT started_at FROM attempts WHERE evidence_digest=? "
                "ORDER BY rowid DESC LIMIT 1",
                (u["upload_id"],),
            ).fetchone()
            if latest and self.wall() < at(latest[0]):
                raise StateError("UPLOAD_CLOCK_ROLLBACK")

    async def eligible(self, row):
        def check(c):
            now = self.wall()
            for material in c.execute(
                "SELECT material_id FROM material_copies WHERE task_id=?", (row["task_id"],)
            ):
                u = c.execute(
                    "SELECT * FROM uploads WHERE material_id=? AND connection_binding=?",
                    (material[0], self.binding),
                ).fetchone()
                if not u or not u["remaining_budget"] or u["state"] in ("rejected", "exhausted"):
                    continue
                if u["state"] == "ready" and u["expires_at"] and at(u["expires_at"]) > now:
                    continue
                a = c.execute(
                    "SELECT * FROM attempts WHERE evidence_digest=? ORDER BY rowid DESC LIMIT 1",
                    (u["upload_id"],),
                ).fetchone()
                if (
                    a
                    and now >= at(a["started_at"])
                    and a["next_attempt_at"]
                    and now < at(a["next_attempt_at"])
                ):
                    return False
            return True

        return await self.db.execute(check, write=False)

    async def prepare(self, row):
        task_id = row["task_id"]
        async with self.locks.setdefault(task_id, asyncio.Lock()):
            async with self.readers.use(task_id):
                materials, details = await self.db.execute(
                    lambda c: (
                        [
                            dict(m)
                            for m in c.execute(
                                "SELECT * FROM material_copies WHERE task_id=? ORDER BY ordinal",
                                (task_id,),
                            )
                        ],
                        json.loads(
                            c.execute(
                                "SELECT details FROM task_events WHERE task_id=? "
                                "AND kind='accepted' ORDER BY event_id LIMIT 1",
                                (task_id,),
                            ).fetchone()[0]
                        ),
                    ),
                    write=False,
                )
                refs = {}
                for material in materials:
                    suffix = next(
                        (
                            m.get("suffix")
                            for m in details.get("materials", [])
                            if m["material_id"] == material["material_id"]
                        ),
                        None,
                    )
                    url = await self._one(row, material, suffix)
                    if url is None:
                        return None
                    refs[material["material_id"]] = url

                def replace(value):
                    if isinstance(value, dict):
                        if set(value) == {"material_id"}:
                            if value["material_id"] not in refs:
                                raise UploadError("UPLOAD_MATERIAL_NOT_REGISTERED")
                            return refs[value["material_id"]]
                        return {k: replace(v) for k, v in value.items()}
                    if isinstance(value, list):
                        return [replace(v) for v in value]
                    return value

                return replace(json.loads(row["effective_parameters"]))

    async def _one(self, task, material, suffix):
        tid, mid, epoch = task["task_id"], material["material_id"], task["epoch"]
        now = self.wall()
        uid = uuid.uuid5(uuid.NAMESPACE_URL, mid + ":" + self.binding).hex
        aid = uuid.uuid4().hex

        def claim(c):
            row = self._eligible(c, tid, epoch)
            current = c.execute(
                "SELECT * FROM material_copies WHERE material_id=? AND task_id=?", (mid, tid)
            ).fetchone()
            if not current or current["state"] != "ready":
                raise StateError("MATERIAL_NOT_READY")
            c.execute(
                "INSERT OR IGNORE INTO uploads VALUES (?,?,?,'',NULL,?,'pending')",
                (uid, mid, self.binding, self.config.limits["UPLOAD_RETRIES"] + 1),
            )
            u = dict(c.execute("SELECT * FROM uploads WHERE upload_id=?", (uid,)).fetchone())
            previous = c.execute(
                "SELECT * FROM attempts WHERE evidence_digest=? ORDER BY rowid DESC LIMIT 1", (uid,)
            ).fetchone()
            if previous and previous["state"] == "intent":
                c.execute(
                    "UPDATE attempts SET state='reconciled',finished_at=? WHERE attempt_id=?",
                    (stamp(now), previous["attempt_id"]),
                )
            if previous and now < at(previous["started_at"]):
                self._attention(c, row, "UPLOAD_CLOCK_ROLLBACK")
                return None
            if u["state"] == "ready" and u["expires_at"] and at(u["expires_at"]) > now:
                return ("cached", u["url"])
            if u["state"] in ("exhausted", "rejected") or not u["remaining_budget"]:
                self._attention(c, row, "UPLOAD_RETRIES_EXHAUSTED")
                return None
            if previous and previous["next_attempt_at"] and now < at(previous["next_attempt_at"]):
                return None
            remaining = u["remaining_budget"] - 1
            used = c.execute(
                "SELECT count(*) FROM attempts WHERE evidence_digest=?", (uid,)
            ).fetchone()[0]
            # Persist the next eligible time before sending, including crash recovery.
            due = stamp(now + min(60, 2 ** min(used, 6)) * random.uniform(1.0, 1.2))
            c.execute(
                "UPDATE uploads SET remaining_budget=?,state='uploading' WHERE upload_id=?",
                (remaining, uid),
            )
            c.execute(
                "INSERT INTO attempts(attempt_id,task_id,phase,round,epoch,state,started_at,"
                "remaining_budget,next_attempt_at,evidence_digest) "
                "VALUES (?,?,?,0,?,'intent',?,?,?,?)",
                (aid, tid, "upload:" + mid, epoch, stamp(now), remaining, due, uid),
            )
            _change(c, row, {"stage": "preparing"}, kind="upload_intent", now=stamp(now))
            return ("send", remaining)

        claimed = await self.db.execute(claim)
        if claimed is None:
            return None
        if claimed[0] == "cached":
            return claimed[1]
        result, failure, temporary, scope = None, None, False, None
        try:
            path = owned_path(self.config.root / "materials", mid + ".input")
            if str(path) != material["managed_path"]:
                raise MaterialError("MATERIAL_OWNERSHIP_INVALID")
            with locked_source(str(path)) as (stream, _):
                result = await self.db.run_effect(
                    aid,
                    lambda: self.send(
                        self.network,
                        stream,
                        suffix=suffix,
                        expected_size=material["size_bytes"],
                        expected_sha256=material["sha256"],
                        byte_limit=self.config.limits["INPUT_BYTES_LIMIT"],
                    ),
                )
        except (ProviderFailure, NetworkError, UploadError, MaterialError, OSError) as error:
            failure = "UPLOAD_FAILED"
            temporary = (isinstance(error, ProviderFailure) and error.temporary) or (
                isinstance(error, NetworkError)
                and str(error)
                in ("NETWORK_TIMEOUT", "NETWORK_REQUEST_FAILED", "NETWORK_DNS_FAILED")
            )
            if isinstance(error, ProviderFailure) and error.scope:
                failure = "UPLOAD_AUTH_OR_PERMISSION"
                scope = error.scope

        # Cancellation deliberately leaves the durable intent and consumed budget.
        def finish(c):
            c.execute(
                "UPDATE attempts SET state='finished',finished_at=? WHERE attempt_id=?",
                (stamp(self.wall()), aid),
            )
            row = _load(c, tid)
            permitted = (
                row["epoch"] == epoch
                and row["auto_mode"] == "active"
                and not row["locally_cancelled"]
                and row["remote_state"] == "not_submitted"
            )
            if not permitted:
                if result is not None:
                    c.execute(
                        "UPDATE uploads SET url=?,expires_at=? WHERE upload_id=?",
                        (
                            result.url,
                            stamp(now + result.expires_in)
                            if result.expires_in is not None
                            else None,
                            uid,
                        ),
                    )
                c.execute("UPDATE uploads SET state='discarded' WHERE upload_id=?", (uid,))
                return None
            if result is not None:
                cutoff = now + result.expires_in if result.expires_in is not None else None
                state = "ready" if cutoff is not None and cutoff > self.wall() else "rejected"
                c.execute(
                    "UPDATE uploads SET url=?,expires_at=?,state=? WHERE upload_id=?",
                    (result.url, stamp(cutoff) if cutoff is not None else None, state, uid),
                )
                c.execute(
                    "INSERT INTO task_events(task_id,version,epoch,kind,recorded_at,details) "
                    "VALUES (?,?,?,'upload_response',?,?)",
                    (
                        tid,
                        row["version"],
                        epoch,
                        stamp(self.wall()),
                        json.dumps(
                            {
                                "material_id": mid,
                                "expires_in": result.expires_in,
                                "file_type": result.file_type,
                                "size": result.size,
                            }
                        ),
                    ),
                )
                if state == "ready":
                    return result.url
                self._attention(c, row, "UPLOAD_EXPIRY_UNVERIFIED_OR_ELAPSED")
            else:
                state = (
                    "pending"
                    if temporary and claimed[1] > 0
                    else "exhausted"
                    if temporary
                    else "rejected"
                )
                c.execute("UPDATE uploads SET state=? WHERE upload_id=?", (state, uid))
                if state != "pending":
                    self._attention(c, row, "UPLOAD_RETRIES_EXHAUSTED" if temporary else failure)
            return None

        value = await self.db.execute(finish)
        if scope:
            raise ProviderFailure("UPLOAD_AUTH_OR_PERMISSION", scope=scope)
        return value
