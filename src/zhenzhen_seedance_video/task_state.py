"""Transactional orthogonal task facts and version/epoch control."""

import json
import uuid

from .cleanup_rules import enqueue_cleanup
from .storage import Database

TERMINAL = frozenset({"succeeded", "failed", "cancelled"})
REMOTE_STATES = {
    "queued": "queued",
    "in_progress": "running",
    "completed": "succeeded",
    "failed": "failed",
}
PUBLIC_FIELDS = (
    "task_id",
    "stage",
    "remote_state",
    "remote_id",
    "auto_mode",
    "delivery",
    "cleanup_state",
    "cancel_requested",
    "locally_cancelled",
    "generation_slot_held",
    "version",
    "epoch",
)


class StateError(RuntimeError):
    def __init__(self, code, snapshot=None):
        super().__init__(code)
        self.snapshot = snapshot


def _load(connection, task_id):
    row = connection.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    if row is None:
        raise StateError("TASK_NOT_FOUND")
    return dict(row)


def _public(row):
    return {key: row[key] for key in PUBLIC_FIELDS} | {"attention": json.loads(row["attention"])}


def _version(row, expected):
    if row["version"] != expected:
        raise StateError("VERSION_CONFLICT", _public(row))


def _change(connection, row, updates, *, kind, now, force=False):
    updates = {key: value for key, value in updates.items() if row[key] != value}
    if not updates and not force:
        return _public(row)
    updates["version"] = row["version"] + 1
    # Names are internal constants, never caller-provided SQL identifiers.
    connection.execute(
        "UPDATE tasks SET " + ",".join(f"{key}=?" for key in updates) + " WHERE task_id=?",
        (*updates.values(), row["task_id"]),
    )
    row.update(updates)
    enqueue_cleanup(connection, row)
    connection.execute(
        """INSERT INTO task_events(task_id,version,epoch,kind,recorded_at,details)
           VALUES (?,?,?,?,?,'{}')""",
        (row["task_id"], row["version"], row["epoch"], kind, now),
    )
    return _public(row)


class TaskState:
    def __init__(self, database: Database):
        self.database = database

    async def get(self, task_id):
        return await self.database.execute(lambda c: _public(_load(c, task_id)), write=False)

    async def begin_submission(
        self,
        task_id,
        *,
        expected_version,
        connection_binding,
        limit,
        now,
        deadline,
        preparation_guard=None,
    ):
        if type(limit) is not int or limit < 1:
            raise StateError("INVALID_GENERATION_LIMIT")

        def transaction(c):
            row = _load(c, task_id)
            _version(row, expected_version)
            if row["connection_binding"] != connection_binding:
                raise StateError("CONNECTION_IDENTITY_UNVERIFIED")
            if (
                row["stage"] not in ("queued", "preparing")
                or row["remote_state"] != "not_submitted"
                or row["auto_mode"] != "active"
                or row["locally_cancelled"]
            ):
                raise StateError("SUBMISSION_NOT_ALLOWED", _public(row))
            if preparation_guard is not None:
                preparation_guard(c, task_id)
            occupied = c.execute("SELECT sum(generation_slot_held) FROM tasks").fetchone()[0] or 0
            if c.execute(
                "SELECT 1 FROM material_copies WHERE task_id=? AND state!='ready'", (task_id,)
            ).fetchone():
                raise StateError("MATERIAL_NOT_READY", _public(row))
            if occupied >= limit:
                raise StateError("GENERATION_CAPACITY_UNAVAILABLE")
            attempt_id = str(uuid.uuid4())
            c.execute(
                """INSERT INTO attempts(attempt_id,task_id,phase,round,epoch,state,
                   started_at,remaining_budget) VALUES (?,?,'submit',?,?,'intent',?,0)""",
                (attempt_id, task_id, row["tracking_round"] + 1, row["epoch"], now),
            )
            result = _change(
                c,
                row,
                {
                    "stage": "submitting",
                    "remote_state": "unknown",
                    "generation_slot_held": 1,
                    "tracking_round": row["tracking_round"] + 1,
                    "tracking_started_at": now,
                    "tracking_deadline": deadline,
                },
                kind="submission_intent",
                now=now,
            )
            return result | {"attempt_id": attempt_id}

        return await self.database.execute(transaction)

    async def cancel_unsubmitted(self, task_id, *, expected_version, now):
        def transaction(c):
            row = _load(c, task_id)
            if row["locally_cancelled"]:
                return _public(row)
            _version(row, expected_version)
            if (
                row["stage"] not in ("queued", "preparing")
                or row["remote_state"] != "not_submitted"
            ):
                raise StateError("REMOTE_CANCEL_CAPABILITY_UNVERIFIED", _public(row))
            return _change(
                c,
                row,
                {
                    "stage": "settled",
                    "locally_cancelled": 1,
                    "cancel_requested": 1,
                    "generation_slot_held": 0,
                    "cleanup_state": "pending",
                    "epoch": row["epoch"] + 1,
                },
                kind="local_cancel",
                now=now,
            )

        return await self.database.execute(transaction)

    async def abandon(self, task_id, *, expected_version, reason, confirmed, now):
        if (
            confirmed is not True
            or not isinstance(reason, str)
            or not reason.strip()
            or len(reason) > 512
        ):
            raise StateError("ABANDON_CONFIRMATION_REQUIRED")

        def transaction(c):
            row = _load(c, task_id)
            # Distinct reasons are distinct management intentions.
            previous = c.execute(
                "SELECT details FROM task_events WHERE task_id=? AND kind='abandon' "
                "ORDER BY event_id DESC LIMIT 1",
                (task_id,),
            ).fetchone()
            if (
                row["auto_mode"] == "abandoned"
                and previous
                and json.loads(previous[0]).get("reason") == reason
            ):
                return _public(row)
            _version(row, expected_version)
            result = _change(
                c,
                row,
                {
                    "auto_mode": "abandoned",
                    "generation_slot_held": 0,
                    "cleanup_state": "pending",
                    "epoch": row["epoch"] + 1,
                },
                kind="abandon",
                now=now,
            )
            c.execute(
                "UPDATE task_events SET details=? WHERE event_id=last_insert_rowid()",
                (json.dumps({"reason": reason}),),
            )
            return result

        return await self.database.execute(transaction)

    async def observe(self, task_id, observation, *, operation_epoch, now):
        """Only already-correlated parser observations enter this internal method.

        Explicit refresh/resume authorization remains the scheduler's job. An
        observation alone never revives stopped automatic execution.
        """

        def transaction(c):
            row = _load(c, task_id)
            if observation.model != row["model"] or (
                row["remote_id"] is not None and row["remote_id"] != observation.remote_id
            ):
                raise StateError("REMOTE_IDENTITY_MISMATCH")
            remote = REMOTE_STATES[observation.status]
            conflict = row["remote_state"] in TERMINAL and row["remote_state"] != remote
            regression = row["remote_state"] == "running" and remote == "queued"
            previous = c.execute(
                "SELECT facts FROM remote_observations WHERE task_id=? "
                "AND terminal_conflict=0 ORDER BY rowid DESC LIMIT 1",
                (task_id,),
            ).fetchone()
            progress_changed = (
                previous is not None
                and json.loads(previous[0]).get("progress") != observation.progress
            )
            c.execute(
                """INSERT INTO remote_observations(observation_id,task_id,epoch,remote_id,
                   raw_status,observed_at,source,facts,terminal_conflict)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    str(uuid.uuid4()),
                    task_id,
                    operation_epoch,
                    observation.remote_id,
                    observation.status,
                    now,
                    "compatibility-parser",
                    json.dumps(
                        {
                            "progress": observation.progress,
                            "url": observation.video_url,
                            "error_code": observation.error_code,
                            "provider_status": observation.provider_status,
                            "last_frame_url": observation.last_frame_url,
                            "draft_task_id": observation.draft_task_id,
                        }
                    ),
                    int(conflict or regression),
                ),
            )
            c.execute("UPDATE tasks SET last_observed_at=? WHERE task_id=?", (now, task_id))
            updates = {"remote_id": observation.remote_id}
            if conflict or regression:
                reason = "REMOTE_TERMINAL_CONFLICT" if conflict else "REMOTE_STATE_REGRESSION"
                reasons = set(json.loads(row["attention"])) | {reason}
                updates["attention"] = json.dumps(sorted(reasons))
                if row["auto_mode"] != "abandoned":
                    updates["auto_mode"] = "needs_attention"
            else:
                updates["remote_state"] = remote
                if remote in TERMINAL:
                    updates["generation_slot_held"] = 0
                current = operation_epoch == row["epoch"] and row["auto_mode"] == "active"
                if (
                    current
                    and remote == "succeeded"
                    and row["delivery"] not in ("ready", "missing", "changed")
                ):
                    updates.update(
                        stage="downloading",
                        delivery="partial" if row["delivery"] == "partial" else "pending",
                    )
                    if observation.attention:
                        updates.update(
                            auto_mode="needs_attention",
                            attention=json.dumps([observation.attention]),
                        )
                elif current and remote == "failed":
                    updates.update(stage="settled", cleanup_state="pending")
            _change(
                c,
                row,
                updates,
                kind="remote_observation",
                now=now,
                force=progress_changed and not conflict and not regression,
            )

            if observation.charge is not None and not conflict and not regression:
                from .charges import record_charge_transaction

                record_charge_transaction(c, task_id, observation.charge, now=now)
            return _public(_load(c, task_id))

        return await self.database.execute(transaction)
