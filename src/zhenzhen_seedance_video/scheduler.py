"""Persistent scheduler driven by an internal adapter; no production adapter is installed."""

import asyncio
import json
import random
import time
import uuid
from datetime import UTC, datetime

from .artifact_manifest import ArtifactManifest
from .material_readers import MaterialReadError, material_readers
from .provider import NotCreatedEvidence, ProviderFailure
from .storage import StorageError
from .task_state import StateError, TaskState, _change, _load, _public, _version

QUERY_ATTENTION = {
    "QUERY_RETRIES_EXHAUSTED",
    "TRACKING_TIMEOUT",
    "SUBMISSION_UNKNOWN",
    "QUERY_REQUEST_TIMEOUT",
    "QUERY_RESPONSE_INVALID",
    "PROVIDER_AUTH_OR_PERMISSION",
    "PROVIDER_RESPONSE_REJECTED",
    "PROVIDER_TEMPORARY",
    "CONNECTION_IDENTITY_UNVERIFIED",
    "CLOCK_ROLLBACK_REQUIRES_REVIEW",
}


def stamp(seconds):
    return datetime.fromtimestamp(seconds, UTC).isoformat()


def seconds(value):
    return datetime.fromisoformat(value).timestamp() if value else None


class Scheduler:
    def __init__(
        self,
        database,
        configuration,
        binding,
        adapter,
        *,
        leases,
        wall=time.time,
        monotonic=time.monotonic,
        delivery=None,
        uploads=None,
    ):
        self.db, self.config, self.binding, self.adapter = database, configuration, binding, adapter
        self.leases, self.wall, self.monotonic = leases, wall, monotonic
        self.delivery = delivery
        self.uploads = uploads
        self.readers = material_readers(database)
        self.state = TaskState(database)
        self._dispatch_lock = asyncio.Lock()
        self._queries = {}
        self._query_slots = asyncio.Semaphore(configuration.limits["QUERY_CONCURRENCY"])
        self._prepare_slots = asyncio.Semaphore(configuration.limits["UPLOAD_CONCURRENCY"])
        self._closed = False
        self._dispatches = set()
        self._wall_start, self._mono_start = wall(), monotonic()

    def now(self):
        # A backwards wall clock cannot buy extra tracking time in a running process.
        return max(self.wall(), self._wall_start + self.monotonic() - self._mono_start)

    async def run(self, stop_event):
        """Internal composition entrypoint; the production backend has no adapter yet."""
        await self.recover()
        if self.delivery is not None:
            await self.delivery.recover()
        workers = {}
        try:
            while not stop_event.is_set() and not self._closed:
                for name, operation in (
                    ("dispatch", self.dispatch),
                    ("poll", self.poll_due),
                    ("delivery", self.deliver_due),
                ):
                    previous = workers.get(name)
                    if previous is None or previous.done():
                        if previous is not None:
                            previous.result()
                        workers[name] = asyncio.create_task(operation())
                try:
                    await asyncio.wait_for(stop_event.wait(), 0.05)
                except TimeoutError:
                    pass
        finally:
            await self.close()
            for worker in workers.values():
                if not worker.done():
                    worker.cancel()
            await asyncio.gather(*workers.values(), return_exceptions=True)

    async def deliver_due(self):
        """Only an injected adapter defines the complete artifact set; no guessed tail frames."""
        if self.delivery is None or not self.leases.network_allowed or self.db.storage_fault:
            return
        rows = await self.db.execute(
            lambda c: [
                dict(r)
                for r in c.execute(
                    "SELECT * FROM tasks t WHERE remote_state='succeeded' AND auto_mode='active' "
                    "AND stage='downloading' AND NOT EXISTS (SELECT 1 FROM artifacts a "
                    "WHERE a.task_id=t.task_id)"
                )
            ],
            write=False,
        )
        for row in rows:
            try:
                references = await self.adapter.artifacts(row)
                if isinstance(references, ArtifactManifest):
                    await self.delivery.register(
                        row["task_id"], references.references, complete=references.complete
                    )
                else:
                    await self.delivery.register(row["task_id"], references)
            except ProviderFailure as error:
                await self._attention(row["task_id"], error.code, row["epoch"])
        await self.delivery.due()

    async def _row(self, task_id):
        return await self.db.execute(lambda c: _load(c, task_id), write=False)

    async def protect(self, scope):
        if scope not in ("all", "seedance-video", "zhenzhen-upscaler") and not scope.startswith(
            "model:"
        ):
            scope = "all"
        await self.db.execute(
            lambda c: (
                c.execute(
                    "INSERT OR REPLACE INTO preferences "
                    "VALUES (?, 'true',1,'provider_adapter',?,NULL)",
                    ("dispatch:" + scope, stamp(self.now())),
                ).rowcount
            )
        )

    async def _blocked(self, row):
        return await self.db.execute(
            lambda c: (
                c.execute(
                    "SELECT 1 FROM preferences WHERE name IN (?,?,?) AND value='true'",
                    ("dispatch:all", "dispatch:" + row["api_id"], "dispatch:model:" + row["model"]),
                ).fetchone()
                is not None
            ),
            write=False,
        )

    async def clear_protection(self, scope, *, evidence):
        if evidence not in ("configuration_repaired_restart", "verified_non_billable_check"):
            raise StateError("PROTECTION_CLEAR_EVIDENCE_REQUIRED")
        await self.db.execute(
            lambda c: (
                c.execute("DELETE FROM preferences WHERE name=?", ("dispatch:" + scope,)).rowcount
            )
        )

    async def _attention(self, task_id, reason, epoch=None):
        def save(c):
            row = _load(c, task_id)
            if epoch is not None and row["epoch"] != epoch or row["auto_mode"] == "abandoned":
                return _public(row)
            return _change(
                c,
                row,
                {
                    "auto_mode": "needs_attention",
                    "attention": json.dumps(sorted(set(json.loads(row["attention"])) | {reason})),
                },
                kind="scheduler_attention",
                now=stamp(self.now()),
            )

        return await self.db.execute(save)

    async def dispatch(self):
        work = asyncio.create_task(self._dispatch())
        self._dispatches.add(work)

        def finished(done):
            self._dispatches.discard(done)
            if not done.cancelled():
                done.exception()

        work.add_done_callback(finished)
        return await asyncio.shield(work)

    async def _dispatch(self):
        if self._closed or not self.leases.dispatch_allowed or self.db.storage_fault:
            return []
        async with self._dispatch_lock:
            occupied = await self.db.execute(
                lambda c: c.execute(
                    "SELECT coalesce(sum(generation_slot_held),0) FROM tasks"
                ).fetchone()[0],
                write=False,
            )
            available = self.config.limits["GENERATION_CONCURRENCY"] - occupied
            if available <= 0:
                return []
            rows = await self.db.execute(
                lambda c: [
                    dict(r)
                    for r in c.execute(
                        "SELECT * FROM tasks WHERE stage IN ('queued','preparing') "
                        "AND remote_state='not_submitted' "
                        "AND auto_mode='active' AND locally_cancelled=0 ORDER BY sequence"
                    )
                ],
                write=False,
            )
            candidates = []
            for row in rows:
                if row["connection_binding"] != self.binding or await self._blocked(row):
                    continue
                unavailable = await self.db.execute(
                    lambda c, tid=row["task_id"]: c.execute(
                        "SELECT 1 FROM material_copies WHERE task_id=? AND state!='ready'", (tid,)
                    ).fetchone(),
                    write=False,
                )
                if not unavailable:
                    if self.uploads is not None and not await self.uploads.eligible(row):
                        continue
                    candidates.append(row)
                if len(candidates) >= min(available, self.config.limits["UPLOAD_CONCURRENCY"]):
                    break

            async def prepare(row):
                async with self._prepare_slots:
                    if self._closed or self.db.storage_fault or not self.leases.dispatch_allowed:
                        return None
                    try:
                        async with asyncio.timeout(self.config.limits["UPLOAD_TIMEOUT_SECONDS"]):
                            async with self.readers.use(row["task_id"]):
                                prepared_row = row
                                if self.uploads is not None:
                                    payload = await self.uploads.prepare(row)
                                    if payload is None:
                                        return None
                                    prepared_row = row | {
                                        "effective_parameters": json.dumps(payload)
                                    }
                                return await self.adapter.prepare(prepared_row)
                    except (MaterialReadError, StateError):
                        return None
                    except asyncio.CancelledError:
                        latest = await self._row(row["task_id"])
                        if latest["auto_mode"] == "abandoned" or latest["locally_cancelled"]:
                            return None
                        raise
                    except ProviderFailure as error:
                        if error.scope:
                            await self.protect(error.scope)
                        else:
                            await self._attention(row["task_id"], error.code, row["epoch"])
                        return None
                    except (TimeoutError, OSError):
                        await self._attention(row["task_id"], "PREPARATION_FAILED", row["epoch"])
                        return None

            prepared = await asyncio.gather(*(prepare(row) for row in candidates))
            results = []
            # Await preparation as a batch, then dispatch in original eligible FIFO order.
            for row, payload in zip(candidates, prepared, strict=True):
                if (
                    payload is None
                    or self._closed
                    or not self.leases.dispatch_allowed
                    or self.db.storage_fault
                ):
                    continue
                if await self._blocked(row):
                    continue
                try:
                    current = await self._row(row["task_id"])
                    duration = self.config.limits["TRACKING_TIMEOUT_SECONDS"]
                    state = await self.state.begin_submission(
                        row["task_id"],
                        expected_version=current["version"],
                        connection_binding=self.binding,
                        limit=self.config.limits["GENERATION_CONCURRENCY"],
                        now=stamp(self.now()),
                        deadline=stamp(self.now() + duration) if duration else None,
                        preparation_guard=self.uploads.guard if self.uploads is not None else None,
                    )
                except StateError as error:
                    if str(error) == "GENERATION_CAPACITY_UNAVAILABLE":
                        break
                    continue
                try:
                    observation = await self.db.run_effect(
                        state["attempt_id"],
                        lambda current=current, payload=payload: self._submit_request(
                            current, payload
                        ),
                    )
                    await self.state.observe(
                        row["task_id"],
                        observation,
                        operation_epoch=state["epoch"],
                        now=stamp(self.now()),
                    )

                    def accepted(c, row=row, state=state):
                        latest = _load(c, row["task_id"])
                        c.execute(
                            "UPDATE attempts SET state='finished',finished_at=? WHERE attempt_id=?",
                            (stamp(self.now()), state["attempt_id"]),
                        )
                        if (
                            latest["epoch"] == state["epoch"]
                            and latest["auto_mode"] == "active"
                            and latest["remote_state"] in ("queued", "running")
                        ):
                            _change(
                                c,
                                latest,
                                {"stage": "tracking"},
                                kind="tracking_started",
                                now=stamp(self.now()),
                            )

                    await self.db.execute(accepted)
                    await self._ensure_query_round(row["task_id"])
                except StorageError:
                    raise
                except (ProviderFailure, TimeoutError, OSError, ValueError) as error:
                    if isinstance(error, ProviderFailure) and error.scope:
                        await self.protect(error.scope)
                    await self._attention(row["task_id"], "SUBMISSION_UNKNOWN", state["epoch"])
                results.append(row["task_id"])
            return results

    async def _ensure_query_round(self, task_id):
        def create(c):
            row = _load(c, task_id)
            existing = c.execute(
                "SELECT attempt_id FROM attempts WHERE task_id=? "
                "AND phase='query_budget' AND round=?",
                (task_id, row["tracking_round"]),
            ).fetchone()
            if not existing and row["remote_id"]:
                c.execute(
                    """INSERT INTO attempts(attempt_id,task_id,phase,round,epoch,state,started_at,
                    remaining_budget,next_attempt_at)
                    VALUES (?,?,'query_budget',?,?,'finished',?,?,?)""",
                    (
                        uuid.uuid4().hex,
                        task_id,
                        row["tracking_round"],
                        row["epoch"],
                        stamp(self.now()),
                        self.config.limits["QUERY_RETRIES"],
                        stamp(self.now()),
                    ),
                )

        await self.db.execute(create)

    async def _budget(self, row):
        await self._ensure_query_round(row["task_id"])
        return await self.db.execute(
            lambda c: dict(
                c.execute(
                    "SELECT * FROM attempts WHERE task_id=? AND phase='query_budget' AND round=?",
                    (row["task_id"], row["tracking_round"]),
                ).fetchone()
            ),
            write=False,
        )

    async def poll_due(self):
        if self._closed or self.db.storage_fault or not self.leases.network_allowed:
            return
        rows = await self.db.execute(
            lambda c: [
                dict(r)
                for r in c.execute(
                    "SELECT * FROM tasks WHERE stage='tracking' AND auto_mode='active' "
                    "AND remote_id IS NOT NULL"
                )
            ],
            write=False,
        )
        operations = []
        for row in rows:
            if row["connection_binding"] != self.binding:
                await self._attention(row["task_id"], "CONNECTION_IDENTITY_UNVERIFIED")
                continue
            budget = await self._budget(row)
            if row["tracking_deadline"] and self.now() >= seconds(row["tracking_deadline"]):
                if row["task_id"] not in self._queries:
                    await self._attention(row["task_id"], "TRACKING_TIMEOUT")
                continue
            if budget["remaining_budget"] <= 0:
                await self._attention(row["task_id"], "QUERY_RETRIES_EXHAUSTED")
            elif not budget["next_attempt_at"] or self.now() >= seconds(budget["next_attempt_at"]):
                operations.append(self.query(row["task_id"]))
        await asyncio.gather(*operations)

    async def query(self, task_id, *, explicit=False):
        if task_id in self._queries:
            return await asyncio.shield(self._queries[task_id])
        task = asyncio.create_task(self._query(task_id, explicit=explicit))
        self._queries[task_id] = task

        def finished(done):
            self._queries.pop(task_id, None)
            if not done.cancelled():
                done.exception()

        task.add_done_callback(finished)
        return await asyncio.shield(task)

    async def _submit_request(self, row, payload):
        async with asyncio.timeout(self.config.limits["REQUEST_TIMEOUT_SECONDS"]):
            return await self.adapter.submit(row, payload)

    async def _query(self, task_id, *, explicit):
        async with self._query_slots:
            row = await self._row(task_id)
            if self._closed or self.db.storage_fault or not self.leases.network_allowed:
                raise StateError("NETWORK_WORK_PAUSED")
            if not row["remote_id"] or row["connection_binding"] != self.binding:
                raise StateError("QUERY_IDENTITY_UNAVAILABLE")
            budget = await self._budget(row)
            if not explicit:
                if row["auto_mode"] != "active":
                    return _public(row)
                if budget["remaining_budget"] <= 0:
                    return await self._attention(task_id, "QUERY_RETRIES_EXHAUSTED")
                if row["tracking_deadline"] and self.now() >= seconds(row["tracking_deadline"]):
                    return await self._attention(task_id, "TRACKING_TIMEOUT")
            try:
                async with asyncio.timeout(self.config.limits["REQUEST_TIMEOUT_SECONDS"]):
                    observation = await self.adapter.query(row)
                result = await self.state.observe(
                    task_id, observation, operation_epoch=row["epoch"], now=stamp(self.now())
                )
            except (ProviderFailure, TimeoutError, OSError, ValueError) as error:
                failure = (
                    error
                    if isinstance(error, ProviderFailure)
                    else ProviderFailure(
                        "QUERY_RESPONSE_INVALID"
                        if isinstance(error, ValueError)
                        else "QUERY_REQUEST_TIMEOUT",
                        temporary=not isinstance(error, ValueError),
                    )
                )
                if failure.scope:
                    await self.protect(failure.scope)
                if not explicit:
                    remaining = max(0, budget["remaining_budget"] - int(failure.temporary))
                    failed = self.config.limits["QUERY_RETRIES"] - remaining
                    await self._record_query(
                        row,
                        budget,
                        remaining,
                        self.now() + min(60, 2**failed * random.uniform(1, 1.25)),
                        "query_failed",
                    )
                    if not remaining or not failure.temporary:
                        await self._attention(
                            task_id,
                            "QUERY_RETRIES_EXHAUSTED" if not remaining else failure.code,
                            row["epoch"],
                        )
                return (await self.state.get(task_id)) | {"query_succeeded": False}
            if not explicit:
                await self._record_query(
                    row,
                    budget,
                    self.config.limits["QUERY_RETRIES"],
                    self.now() + self.config.limits["POLL_INTERVAL_SECONDS"],
                    "query_succeeded",
                )
                if result["remote_state"] not in ("succeeded", "failed", "cancelled") and (
                    row["tracking_deadline"] and self.now() >= seconds(row["tracking_deadline"])
                ):
                    result = await self._attention(task_id, "TRACKING_TIMEOUT", row["epoch"])
            return result | {"query_succeeded": True, "refresh_attention": observation.attention}

    async def _record_query(self, row, budget, remaining, due, kind):
        def record(c):
            c.execute(
                "UPDATE attempts SET remaining_budget=?,next_attempt_at=? WHERE attempt_id=?",
                (remaining, stamp(due), budget["attempt_id"]),
            )
            c.execute(
                """INSERT INTO task_events(task_id,version,epoch,kind,recorded_at,details)
                         VALUES (?,?,?,?,?,?)""",
                (
                    row["task_id"],
                    row["version"],
                    row["epoch"],
                    kind,
                    stamp(self.now()),
                    json.dumps({"round": row["tracking_round"], "remaining_budget": remaining}),
                ),
            )

        await self.db.execute(record)

    async def refresh(self, task_id):
        before = await self._row(task_id)
        result = await self.query(task_id, explicit=True)
        if not result.get("query_succeeded"):
            return result

        def authorize_result(c):
            row = _load(c, task_id)
            if row["epoch"] != before["epoch"]:
                return _public(row)
            if row["remote_state"] not in ("succeeded", "failed", "cancelled"):
                return _public(row)  # A running refresh does not start automatic polling.
            reasons = set(json.loads(row["attention"]))
            if result.get("refresh_attention"):
                reasons.add(result["refresh_attention"])
            reasons -= QUERY_ATTENTION
            if "REMOTE_TERMINAL_CONFLICT" in reasons or "REMOTE_STATE_REGRESSION" in reasons:
                return _public(row)
            updates = {"attention": json.dumps(sorted(reasons)), "generation_slot_held": 0}
            if row["remote_state"] == "succeeded":
                updates.update(
                    auto_mode="needs_attention"
                    if reasons - {"ARTIFACT_SET_UNVERIFIED"}
                    else "active"
                )
                if row["delivery"] not in ("ready", "missing", "changed"):
                    updates.update(
                        stage="downloading",
                        delivery="partial" if row["delivery"] == "partial" else "pending",
                    )
            else:
                updates.update(stage="settled", cleanup_state="pending", auto_mode="active")
            return _change(c, row, updates, kind="explicit_refresh_result", now=stamp(self.now()))

        return await self.db.execute(authorize_result)

    async def resume(self, task_id, *, expected_version):
        def resume(c):
            row = _load(c, task_id)
            if row["auto_mode"] == "active" and row["stage"] == "tracking":
                return _public(row)
            _version(row, expected_version)
            if not row["remote_id"] or row["remote_state"] in ("succeeded", "failed", "cancelled"):
                raise StateError("TRACKING_RESUME_NOT_ALLOWED", _public(row))
            if row["connection_binding"] != self.binding:
                raise StateError("CONNECTION_IDENTITY_UNVERIFIED")
            if not row["generation_slot_held"]:
                occupied = (
                    c.execute("SELECT sum(generation_slot_held) FROM tasks").fetchone()[0] or 0
                )
                if occupied >= self.config.limits["GENERATION_CONCURRENCY"]:
                    raise StateError("GENERATION_CAPACITY_UNAVAILABLE")
            duration = self.config.limits["TRACKING_TIMEOUT_SECONDS"]
            reasons = set(json.loads(row["attention"]))
            reasons -= QUERY_ATTENTION
            if reasons:
                raise StateError("UNRESOLVED_TASK_ATTENTION", _public(row))
            result = _change(
                c,
                row,
                {
                    "auto_mode": "active",
                    "stage": "tracking",
                    "attention": "[]",
                    "generation_slot_held": 1,
                    "epoch": row["epoch"] + 1,
                    "tracking_round": row["tracking_round"] + 1,
                    "tracking_started_at": stamp(self.now()),
                    "tracking_deadline": stamp(self.now() + duration) if duration else None,
                },
                kind="tracking_resumed",
                now=stamp(self.now()),
            )
            return result

        result = await self.db.execute(resume)
        await self._ensure_query_round(task_id)
        return result

    async def recover(self):
        if self.uploads is not None:
            await self.uploads.recover()
        rows = await self.db.execute(
            lambda c: [dict(r) for r in c.execute("SELECT * FROM tasks")], write=False
        )
        for row in rows:
            if row["auto_mode"] != "active":
                continue
            if row["connection_binding"] != self.binding:
                await self._attention(row["task_id"], "CONNECTION_IDENTITY_UNVERIFIED")
            elif row["stage"] == "submitting":
                await self._attention(row["task_id"], "SUBMISSION_UNKNOWN")
            elif row["stage"] == "tracking":
                latest = max(
                    seconds(row["tracking_started_at"]) or 0, seconds(row["last_observed_at"]) or 0
                )
                if self.wall() < latest:
                    await self._attention(row["task_id"], "CLOCK_ROLLBACK_REQUIRES_REVIEW")
                    continue
                budget = await self._budget(row)
                if budget["remaining_budget"] <= 0:
                    await self._attention(row["task_id"], "QUERY_RETRIES_EXHAUSTED")
                elif row["tracking_deadline"] and self.now() >= seconds(row["tracking_deadline"]):
                    await self._attention(row["task_id"], "TRACKING_TIMEOUT")

    async def retry_not_created(self, task_id, *, expected_version):
        self.adapter.capabilities.require("submission_lookup")
        row = await self._row(task_id)
        evidence = await self.adapter.prove_not_created(row)
        if (
            not isinstance(evidence, NotCreatedEvidence)
            or not evidence.source
            or not evidence.digest
        ):
            raise StateError("NOT_CREATED_EVIDENCE_REQUIRED")

        def reset(c):
            current = _load(c, task_id)
            _version(current, expected_version)
            if (
                current["stage"] != "submitting"
                or current["remote_id"] is not None
                or current["auto_mode"] == "abandoned"
                or current["locally_cancelled"]
            ):
                raise StateError("SUBMISSION_RETRY_NOT_ALLOWED")
            c.execute(
                "UPDATE attempts SET state='reconciled',finished_at=? WHERE task_id=? "
                "AND phase='submit' AND state='intent'",
                (stamp(self.now()), task_id),
            )
            result = _change(
                c,
                current,
                {
                    "stage": "queued",
                    "remote_state": "not_submitted",
                    "auto_mode": "active",
                    "generation_slot_held": 0,
                    "attention": "[]",
                    "epoch": current["epoch"] + 1,
                },
                kind="verified_not_created_retry",
                now=stamp(self.now()),
            )

            c.execute(
                "UPDATE task_events SET details=? WHERE event_id=last_insert_rowid()",
                (json.dumps({"source": evidence.source, "digest": evidence.digest}),),
            )
            return result

        return await self.db.execute(reset)

    async def close(self):
        self._closed = True
        if self.delivery is not None:
            await self.delivery.close()
        tasks = list(self._queries.values()) + list(self._dispatches)
        if tasks:
            done, pending = await asyncio.wait(
                tasks, timeout=self.config.limits["SHUTDOWN_DRAIN_SECONDS"]
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
