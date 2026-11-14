"""Local consistent snapshots and signed, filter-bound live pagination."""

import asyncio
import hashlib
import hmac
import json
import math
import secrets
import time

from .artifact_manifest import completeness
from .task_state import StateError, _load, _public


class Queries:
    def __init__(self, database, configuration):
        self.db, self.config = database, configuration
        self.key = secrets.token_bytes(32)

    def snapshot(self, c, row):
        value = _public(row)
        event = c.execute(
            "SELECT recorded_at FROM task_events WHERE task_id=? ORDER BY event_id DESC LIMIT 1",
            (row["task_id"],),
        ).fetchone()
        accepted = c.execute(
            "SELECT details FROM task_events WHERE task_id=? AND kind='accepted' LIMIT 1",
            (row["task_id"],),
        ).fetchone()
        details = json.loads(accepted[0]) if accepted else {}
        parameters = json.loads(row["effective_parameters"])
        metadata = parameters.get("metadata", {})
        value.update(
            model=row["model"],
            api_id=row["api_id"],
            kind=row["kind"],
            updated_at=event[0] if event else row["created_at"],
            last_observed_at=row["last_observed_at"],
            stale=self.db.storage_fault,
            authorization=details.get("authorization"),
            effective_summary={
                "seconds": parameters.get("seconds"),
                **{k: metadata.get(k) for k in ("duration", "resolution", "ratio", "draft")},
            },
            charge={
                "state": row["charge_state"],
                "amount": row["actual_amount"],
                "currency": row["actual_currency"],
            },
            artifact_set_status="unverified"
            if not completeness(c, row["task_id"])
            else "confirmed"
            if c.execute("SELECT 1 FROM artifacts WHERE task_id=?", (row["task_id"],)).fetchone()
            else "unregistered",
            artifact_counts={
                r[0]: r[1]
                for r in c.execute(
                    "SELECT state,count(*) FROM artifacts WHERE task_id=? GROUP BY state",
                    (row["task_id"],),
                )
            },
        )
        actions = ["get_task", "wait_task", "list_artifacts"]
        if row["remote_state"] == "not_submitted" and not row["locally_cancelled"]:
            actions += ["cancel_task", "repair_task_materials"]
        if row["remote_id"]:
            actions += ["refresh_task", "resume_task_tracking"]
        if row["delivery"] in ("pending", "partial", "missing", "changed"):
            actions.append("retry_task_download")
        if row["cleanup_state"] == "failed":
            actions.append("retry_material_cleanup")
        if row["auto_mode"] != "abandoned":
            actions.append("abandon_task")
        value["allowed_actions"] = actions
        observation = c.execute(
            "SELECT raw_status,facts FROM remote_observations WHERE task_id=? "
            "AND terminal_conflict=0 ORDER BY rowid DESC LIMIT 1",
            (row["task_id"],),
        ).fetchone()
        if observation:
            facts = json.loads(observation[1])
            # Older rows may contain only the normalized status. Do not invent
            # an upstream spelling, or expose arbitrary persisted response text.
            normalized = observation[0]
            upstream = facts.get("provider_status")
            aliases = {
                "queued": {"queued", "NOT_START"},
                "in_progress": {"in_progress", "IN_PROGRESS"},
                "completed": {"completed", "SUCCESS"},
                "failed": {"failed"},
            }
            value["normalized_status"] = normalized
            value["raw_status"] = (
                upstream
                if isinstance(upstream, str) and upstream in aliases.get(normalized, set())
                else None
            )
            progress = facts.get("progress")
            draft_id = facts.get("draft_task_id")
            if observation[0] == "completed" and draft_id and draft_id == row["remote_id"]:
                value["draft_task_id"] = draft_id
            if observation[0] == "failed" and facts.get("error_code") in (
                "video_generation_failed",
                "REMOTE_TASK_FAILED",
            ):
                value["remote_error_code"] = facts["error_code"]
            if type(progress) in (int, float) and math.isfinite(progress) and 0 <= progress <= 100:
                value["progress"] = progress
        return value

    async def get(self, task_id):
        return await self.db.execute(lambda c: self.snapshot(c, _load(c, task_id)), write=False)

    def cursor(self, sequence, filters):
        payload = json.dumps([sequence, filters], separators=(",", ":"), sort_keys=True)
        return (
            str(sequence) + "." + hmac.new(self.key, payload.encode(), hashlib.sha256).hexdigest()
        )

    async def list(
        self,
        *,
        cursor=None,
        limit=None,
        remote_state=None,
        attention_reason=None,
        needs_attention=False,
    ):
        limit = self.config.limits["PAGE_DEFAULT_SIZE"] if limit is None else limit
        if type(limit) is not int or not 1 <= limit <= self.config.limits["PAGE_MAX_SIZE"]:
            raise ValueError("INVALID_PAGE_SIZE")
        filters = [remote_state, attention_reason, needs_attention]
        sequence = 0
        if cursor is not None:
            if not isinstance(cursor, str) or len(cursor) > 100:
                raise ValueError("INVALID_CURSOR")
            try:
                sequence = int(cursor.split(".")[0])
                if sequence < 0 or not hmac.compare_digest(cursor, self.cursor(sequence, filters)):
                    raise ValueError()
            except (ValueError, IndexError):
                raise ValueError("INVALID_CURSOR") from None

        def read(c):
            rows = c.execute(
                """SELECT * FROM tasks WHERE sequence>? AND (? IS NULL OR remote_state=?)
                AND (?=0 OR attention!='[]') AND (? IS NULL OR EXISTS
                (SELECT 1 FROM json_each(tasks.attention) WHERE value=?))
                ORDER BY sequence LIMIT ?""",
                (
                    sequence,
                    remote_state,
                    remote_state,
                    needs_attention,
                    attention_reason,
                    attention_reason,
                    limit + 1,
                ),
            ).fetchall()
            items = []
            last = sequence
            budget = self.config.limits["TOOL_RESPONSE_BYTES_LIMIT"] - 512
            for row in rows[:limit]:
                item = self.snapshot(c, dict(row))
                if len(json.dumps(items + [item], ensure_ascii=False).encode()) > budget:
                    break
                items.append(item)
                last = row["sequence"]
            if rows and not items:
                raise StateError("RESPONSE_LIMIT_TOO_SMALL")
            return {
                "items": items,
                "next_cursor": self.cursor(last, filters) if len(rows) > len(items) else None,
                "cross_page_snapshot": False,
                "stale": self.db.storage_fault,
            }

        return await self.db.execute(read, write=False)

    async def wait(self, task_id, after_version, timeout_seconds=None):
        timeout_seconds = (
            self.config.limits["WAIT_DEFAULT_SECONDS"]
            if timeout_seconds is None
            else timeout_seconds
        )
        if (
            type(after_version) is not int
            or after_version < 0
            or type(timeout_seconds) not in (int, float)
            or not math.isfinite(timeout_seconds)
            or not 0 <= timeout_seconds <= self.config.limits["WAIT_MAX_SECONDS"]
        ):
            raise ValueError("INVALID_WAIT")
        deadline = time.monotonic() + timeout_seconds
        while True:
            result = await self.get(task_id)
            if result["version"] != after_version:
                return result | {"wait_timed_out": False}
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return result | {"wait_timed_out": True}
            await asyncio.sleep(min(0.05, remaining))
