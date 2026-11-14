"""Ordered startup reconciliation and one drain budget for background work."""

import asyncio
import json
from datetime import UTC, datetime

from .storage import StorageError
from .task_state import _change


class Lifecycle:
    def __init__(self, admission, artifacts, cleanup, binding, leases, scheduler=None):
        self.admission, self.artifacts, self.cleanup = admission, artifacts, cleanup
        self.db, self.config = admission.db, admission.config
        self.binding, self.leases, self.scheduler = binding, leases, scheduler
        self.workers = {}
        self.ready = False
        self.stopping = False

    async def recover(self):
        if self.ready:
            return
        await self.admission.recover()

        def reconcile(c):
            for record in c.execute("SELECT * FROM tasks").fetchall():
                row = dict(record)
                terminal = row["remote_state"] in ("succeeded", "failed", "cancelled")
                held = int(
                    not terminal
                    and not row["locally_cancelled"]
                    and row["auto_mode"] != "abandoned"
                    and (
                        row["stage"] in ("submitting", "tracking")
                        or row["remote_state"] in ("unknown", "queued", "running")
                    )
                )
                updates = {"generation_slot_held": held}
                reasons = set(json.loads(row["attention"]))
                if row["auto_mode"] == "active" and not row["locally_cancelled"]:
                    if row["connection_binding"] != self.binding and row["stage"] != "settled":
                        reasons.add("CONNECTION_IDENTITY_UNVERIFIED")
                    elif terminal:
                        if row["remote_state"] == "succeeded" and row["delivery"] != "ready":
                            updates.update(
                                stage="downloading",
                                delivery=row["delivery"]
                                if row["delivery"] != "none"
                                else "pending",
                            )
                        else:
                            updates["stage"] = "settled"
                    elif row["stage"] == "submitting":
                        if row["remote_id"] and row["remote_state"] in ("queued", "running"):
                            updates["stage"] = "tracking"
                            c.execute(
                                "UPDATE attempts SET state='reconciled' WHERE task_id=? "
                                "AND phase='submit' AND state='intent'",
                                (row["task_id"],),
                            )
                        elif not terminal:
                            reasons.add("SUBMISSION_UNKNOWN")
                    elif row["stage"] == "preparing":
                        updates["stage"] = "queued"
                    blocking = reasons - (
                        {"ARTIFACT_SET_UNVERIFIED"} if row["remote_state"] == "succeeded" else set()
                    )
                    if blocking:
                        updates.update(
                            auto_mode="needs_attention", attention=json.dumps(sorted(reasons))
                        )
                _change(
                    c, row, updates, kind="startup_reconciled", now=datetime.now(UTC).isoformat()
                )

        await self.db.execute(reconcile)
        if self.scheduler:
            await self.scheduler.recover()
        await self.artifacts.recover()
        await self.cleanup.scan()
        self.ready = True

    def active(self):
        tasks = (
            set(self.workers.values()) | set(self.artifacts.work.values()) | set(self.cleanup.work)
        )
        if self.scheduler:
            tasks |= set(self.scheduler._queries.values()) | set(self.scheduler._dispatches)
        return {task for task in tasks if not task.done()}

    @property
    def idle(self):
        return not self.active()

    async def run(self):
        if not self.ready:
            raise RuntimeError("RECOVERY_REQUIRED")
        try:
            while not self.stopping:
                operations = {"cleanup": self.cleanup.due}
                if self.scheduler:
                    operations.update(
                        dispatch=self.scheduler.dispatch,
                        query=self.scheduler.poll_due,
                        delivery=self.scheduler.deliver_due,
                    )
                for name, operation in operations.items():
                    previous = self.workers.get(name)
                    if previous and previous.done():
                        try:
                            previous.result()
                        except StorageError:
                            if not self.db.storage_fault:
                                raise
                    if (
                        self.leases.network_allowed
                        and not self.db.storage_fault
                        and (previous is None or previous.done())
                    ):
                        self.workers[name] = asyncio.create_task(operation())
                await asyncio.sleep(0.05)
        finally:
            self.stopping = True

    async def close(self):
        self.stopping = True
        if self.scheduler:
            self.scheduler._closed = True
        self.artifacts.closed = True
        self.cleanup.closed = True
        remaining = self.config.limits["SHUTDOWN_DRAIN_SECONDS"]
        if self.leases.draining_since is not None:
            remaining = max(0, self.leases.draining_since + remaining - self.leases.clock())
        tasks = self.active()
        if tasks:
            _, pending = await asyncio.wait(tasks, timeout=remaining)
            # Shielded suboperations are included explicitly, not just their callers.
            pending |= self.active()
            for task in pending:
                task.cancel()
            await asyncio.gather(*tasks, *pending, return_exceptions=True)
        await self.admission.close()
