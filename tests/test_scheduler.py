import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest

from zhenzhen_seedance_video.admission import AdmissionService
from zhenzhen_seedance_video.config import load_configuration
from zhenzhen_seedance_video.provider import Capabilities, ProviderFailure
from zhenzhen_seedance_video.provider_response import Observation
from zhenzhen_seedance_video.scheduler import Scheduler
from zhenzhen_seedance_video.storage import Database


class SyntheticAdapter:
    capabilities = Capabilities()

    def __init__(self):
        self.posts = []
        self.queries = []
        self.query_failure = False
        self.submit_failure = False
        self.status = "in_progress"

    async def prepare(self, row):
        return {"synthetic": True}

    async def submit(self, row, payload):
        self.posts.append(row["task_id"])
        if self.submit_failure:
            raise ProviderFailure()
        return Observation(
            "synthetic-" + row["task_id"], row["model"], "queued", 0, None, None, None
        )

    async def query(self, row):
        self.queries.append(row["task_id"])
        if self.query_failure:
            raise ProviderFailure("TEMPORARY_QUERY", temporary=True)
        return Observation(
            row["remote_id"],
            row["model"],
            self.status,
            50,
            "https://synthetic.example/video" if self.status == "completed" else None,
            None,
            None,
        )


@pytest.fixture
async def setup(monkeypatch, clock):
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_API_KEY", "synthetic")
    config = load_configuration()
    config = replace(
        config, limits=dict(config.limits) | {"QUERY_RETRIES": 2, "GENERATION_CONCURRENCY": 2}
    )
    db = Database(config.state_dir)
    admission = AdmissionService(db, config, "binding")
    adapter = SyntheticAdapter()
    leases = SimpleNamespace(dispatch_allowed=True, network_allowed=True)
    scheduler = Scheduler(
        db,
        config,
        "binding",
        adapter,
        leases=leases,
        wall=lambda: clock.utc,
        monotonic=lambda: clock.monotonic,
    )
    try:
        yield scheduler, admission, adapter, leases, clock
    finally:
        await scheduler.close()
        await admission.close()
        await db.close()


async def submit(admission, key, upscale=False):
    if upscale:
        return await admission.submit(
            key,
            {
                "model": "zhenzhen-upscaler",
                "metadata": {
                    "content": [
                        {
                            "type": "video_url",
                            "video_url": {"url": "https://synthetic.example/input"},
                        }
                    ]
                },
            },
            api_id="zhenzhen-upscaler",
        )
    return await admission.submit(key, {"model": "seedance-2.0-mini-t2v", "prompt": "synthetic"})


async def test_fifo_protection_global_capacity_and_host_gate(setup):
    engine, admission, adapter, leases, clock = setup
    a1 = await submit(admission, "a1")
    b1 = await submit(admission, "b1", True)
    a2 = await submit(admission, "a2")
    b2 = await submit(admission, "b2", True)
    await engine.protect("seedance-video")
    leases.dispatch_allowed = False
    assert await engine.dispatch() == []
    leases.dispatch_allowed = True
    assert await engine.dispatch() == [b1["task_id"], b2["task_id"]]
    await engine.clear_protection("seedance-video", evidence="configuration_repaired_restart")
    assert await engine.dispatch() == []
    adapter.status = "completed"
    await engine.poll_due()
    assert await engine.dispatch() == [a1["task_id"], a2["task_id"]]


async def test_unknown_submit_survives_restart_without_duplicate(setup):
    engine, admission, adapter, leases, clock = setup
    task = await submit(admission, "unknown")
    adapter.submit_failure = True
    await engine.dispatch()
    row = await engine.state.get(task["task_id"])
    assert row["remote_state"] == "unknown" and row["generation_slot_held"] == 1
    assert row["auto_mode"] == "needs_attention"
    await engine.recover()
    adapter.submit_failure = False
    await engine.dispatch()
    assert adapter.posts == [task["task_id"]]
    with pytest.raises(ProviderFailure, match="CAPABILITY_UNVERIFIED"):
        await engine.retry_not_created(task["task_id"], expected_version=row["version"])


async def test_query_exhaustion_backoff_restart_and_success_no_budget_cost(setup):
    engine, admission, adapter, leases, clock = setup
    task = await submit(admission, "query")
    await engine.dispatch()
    await engine.poll_due()
    row = await engine._row(task["task_id"])
    assert (await engine._budget(row))["remaining_budget"] == 2
    clock.advance(6)
    adapter.query_failure = True
    await engine.poll_due()
    row = await engine._row(task["task_id"])
    assert (await engine._budget(row))["remaining_budget"] == 1
    await engine.poll_due()
    assert len(adapter.queries) == 2
    clock.advance(3)
    await engine.poll_due()
    assert (await engine.state.get(task["task_id"]))["auto_mode"] == "needs_attention"
    await engine.recover()
    adapter.query_failure = False
    clock.advance(100)
    await engine.poll_due()
    assert len(adapter.queries) == 3


async def test_cancel_and_abandon_late_submission_facts(setup):
    engine, admission, adapter, leases, clock = setup
    cancelled = await submit(admission, "cancelled")
    await engine.state.cancel_unsubmitted(cancelled["task_id"], expected_version=1, now="now")
    assert await engine.dispatch() == []
    task = await submit(admission, "late")
    entered, release = asyncio.Event(), asyncio.Event()
    original = adapter.submit

    async def delayed(row, payload):
        entered.set()
        await release.wait()
        return await original(row, payload)

    adapter.submit = delayed
    work = asyncio.create_task(engine.dispatch())
    await entered.wait()
    row = await engine.state.get(task["task_id"])
    await engine.state.abandon(
        task["task_id"],
        expected_version=row["version"],
        reason="explicit",
        confirmed=True,
        now="now",
    )
    release.set()
    await work
    final = await engine.state.get(task["task_id"])
    assert (
        final["remote_id"]
        and final["auto_mode"] == "abandoned"
        and not final["generation_slot_held"]
    )


async def test_preparation_completion_does_not_reorder(setup):
    engine, admission, adapter, leases, clock = setup
    a = await submit(admission, "first")
    b = await submit(admission, "second")

    async def prepare(row):
        if row["task_id"] == a["task_id"]:
            await asyncio.sleep(0.02)
        return {}

    adapter.prepare = prepare
    await engine.dispatch()
    assert adapter.posts == [a["task_id"], b["task_id"]]


async def test_refresh_merge_and_resume_new_budget(setup):
    engine, admission, adapter, leases, clock = setup
    task = await submit(admission, "refresh")
    await engine.dispatch()
    await engine._attention(task["task_id"], "QUERY_RETRIES_EXHAUSTED")
    entered, release = asyncio.Event(), asyncio.Event()
    original = adapter.query

    async def delayed(row):
        entered.set()
        await release.wait()
        return await original(row)

    adapter.query = delayed
    first = asyncio.create_task(engine.refresh(task["task_id"]))
    await entered.wait()
    second = asyncio.create_task(engine.refresh(task["task_id"]))
    await asyncio.sleep(0)
    release.set()
    one, two = await asyncio.gather(first, second)
    assert len(adapter.queries) == 1 and one["auto_mode"] == "needs_attention"
    resumed = await engine.resume(task["task_id"], expected_version=one["version"])
    assert resumed["auto_mode"] == "active"
    assert await engine.resume(task["task_id"], expected_version=one["version"]) == resumed
    row = await engine._row(task["task_id"])
    assert row["tracking_round"] == 2 and (await engine._budget(row))["remaining_budget"] == 2


async def test_abandoned_refresh_success_authorizes_download_but_old_query_does_not(setup):
    engine, admission, adapter, leases, clock = setup
    task = await submit(admission, "abandon-refresh")
    await engine.dispatch()
    row = await engine.state.get(task["task_id"])
    await engine.state.abandon(
        task["task_id"], expected_version=row["version"], reason="stop", confirmed=True, now="now"
    )
    adapter.status = "completed"
    refreshed = await engine.refresh(task["task_id"])
    assert refreshed["delivery"] == "pending" and refreshed["auto_mode"] == "active"
    assert not refreshed["generation_slot_held"]


async def test_resume_abandoned_requires_capacity(setup):
    engine, admission, adapter, leases, clock = setup
    task = await submit(admission, "abandoned")
    await engine.dispatch()
    row = await engine.state.get(task["task_id"])
    abandoned = await engine.state.abandon(
        task["task_id"], expected_version=row["version"], reason="stop", confirmed=True, now="now"
    )
    await submit(admission, "new1")
    await submit(admission, "new2")
    await engine.dispatch()
    from zhenzhen_seedance_video.task_state import StateError

    with pytest.raises(StateError, match="CAPACITY_UNAVAILABLE"):
        await engine.resume(task["task_id"], expected_version=abandoned["version"])
    assert (await engine.refresh(task["task_id"]))["auto_mode"] == "abandoned"


async def test_tracking_deadline_and_wall_rollback(setup):
    engine, admission, adapter, leases, clock = setup
    engine.config = replace(
        engine.config, limits=dict(engine.config.limits) | {"TRACKING_TIMEOUT_SECONDS": 5}
    )
    task = await submit(admission, "deadline")
    clock.advance(100)  # Queue time is excluded.
    await engine.dispatch()
    clock.utc -= 1000
    clock.monotonic += 6
    await engine.poll_due()
    row = await engine.state.get(task["task_id"])
    assert "TRACKING_TIMEOUT" in row["attention"] and row["generation_slot_held"] == 1
    assert not adapter.queries


async def test_inflight_query_success_can_finish_past_tracking_deadline(setup):
    engine, admission, adapter, leases, clock = setup
    engine.config = replace(
        engine.config, limits=dict(engine.config.limits) | {"TRACKING_TIMEOUT_SECONDS": 5}
    )
    task = await submit(admission, "late-success")
    await engine.dispatch()
    original = adapter.query

    async def delayed(row):
        clock.advance(6)
        adapter.status = "completed"
        return await original(row)

    adapter.query = delayed
    await engine.poll_due()
    row = await engine.state.get(task["task_id"])
    assert row["remote_state"] == "succeeded" and row["delivery"] == "pending"


async def test_query_timeout_uses_budget_and_no_retry_after_exhaustion(setup):
    engine, admission, adapter, leases, clock = setup
    engine.config = replace(
        engine.config,
        limits=dict(engine.config.limits) | {"REQUEST_TIMEOUT_SECONDS": 0.01, "QUERY_RETRIES": 1},
    )
    task = await submit(admission, "timeout")
    await engine.dispatch()

    async def slow(row):
        await asyncio.sleep(10)

    adapter.query = slow
    await engine.poll_due()
    row = await engine.state.get(task["task_id"])
    assert "QUERY_RETRIES_EXHAUSTED" in row["attention"]


async def test_submit_response_before_failed_commit_is_not_reposted(setup, monkeypatch):
    engine, admission, adapter, leases, clock = setup
    from zhenzhen_seedance_video.storage import StorageError

    task = await submit(admission, "commit-failure")
    original = engine.state.observe

    async def fail(*args, **kwargs):
        raise StorageError("STORAGE_FAULT")

    monkeypatch.setattr(engine.state, "observe", fail)
    with pytest.raises(StorageError):
        await engine.dispatch()
    monkeypatch.setattr(engine.state, "observe", original)
    await engine.recover()
    await engine.dispatch()
    assert adapter.posts == [task["task_id"]]
    row = await engine.state.get(task["task_id"])
    assert row["remote_state"] == "unknown" and row["generation_slot_held"] == 1


async def test_verified_not_created_requires_explicit_retry(setup):
    engine, admission, adapter, leases, clock = setup
    from zhenzhen_seedance_video.provider import NotCreatedEvidence

    task = await submit(admission, "not-created")
    adapter.submit_failure = True
    await engine.dispatch()

    class TestCapabilities(Capabilities):
        submission_lookup = True

    adapter.capabilities = TestCapabilities()

    async def proof(row):
        return NotCreatedEvidence("synthetic-fixture", "synthetic-digest")

    adapter.prove_not_created = proof
    row = await engine.state.get(task["task_id"])
    await engine.retry_not_created(task["task_id"], expected_version=row["version"])
    adapter.submit_failure = False
    await engine.recover()
    await engine.dispatch()
    assert adapter.posts == [task["task_id"], task["task_id"]]


async def test_restart_budget_identity_output_and_lower_limit(setup):
    engine, admission, adapter, leases, clock = setup
    a = await submit(admission, "a")
    b = await submit(admission, "b")
    await engine.dispatch()
    adapter.query_failure = True
    await engine.poll_due()
    original = await engine._row(a["task_id"])
    budget = await engine._budget(original)
    await engine.db.close()
    database = Database(engine.config.state_dir)
    configuration = replace(
        engine.config,
        output_dir=engine.config.root / "changed-output",
        limits=dict(engine.config.limits) | {"GENERATION_CONCURRENCY": 1},
    )
    restored = Scheduler(
        database,
        configuration,
        "binding",
        adapter,
        leases=leases,
        wall=lambda: clock.utc,
        monotonic=lambda: clock.monotonic,
    )
    try:
        await restored.recover()
        row = await restored._row(a["task_id"])
        assert row["output_dir"] == original["output_dir"]
        assert await restored._budget(row) == budget
        assert (await restored.state.get(a["task_id"]))["generation_slot_held"] == 1
        assert (await restored.state.get(b["task_id"]))["generation_slot_held"] == 1
        assert await restored.dispatch() == []
        restored.binding = "changed-binding"
        await restored.recover()
        assert (
            "CONNECTION_IDENTITY_UNVERIFIED"
            in (await restored.state.get(a["task_id"]))["attention"]
        )
        assert (await restored.state.get(a["task_id"]))["generation_slot_held"] == 1
    finally:
        await restored.close()
        await database.close()


async def test_storage_gate_before_post_and_submit_intent_visible(setup):
    engine, admission, adapter, leases, clock = setup
    task = await submit(admission, "gate")
    engine.db._fault.set()
    assert await engine.dispatch() == [] and not adapter.posts
    engine.db._fault.clear()  # Test-only setup; production requires Database.reconcile.
    original = adapter.submit

    async def inspect(row, payload):
        stored = await engine._row(row["task_id"])
        assert stored["generation_slot_held"] == 1 and stored["remote_state"] == "unknown"
        assert await engine.db.pending_intents()
        return await original(row, payload)

    adapter.submit = inspect
    await engine.dispatch()
    assert adapter.posts == [task["task_id"]]


async def test_bounded_shutdown_cancels_query_without_resubmission(setup):
    engine, admission, adapter, leases, clock = setup
    engine.config = replace(
        engine.config, limits=dict(engine.config.limits) | {"SHUTDOWN_DRAIN_SECONDS": 0.01}
    )
    task = await submit(admission, "shutdown")
    await engine.dispatch()
    entered = asyncio.Event()

    async def hanging(row):
        entered.set()
        await asyncio.sleep(10)

    adapter.query = hanging
    query = asyncio.create_task(engine.query(task["task_id"]))
    await entered.wait()
    await engine.close()
    with pytest.raises(asyncio.CancelledError):
        await query
    row = await engine.state.get(task["task_id"])
    assert row["generation_slot_held"] == 1 and adapter.posts == [task["task_id"]]


def test_http_status_never_proves_not_created():
    from zhenzhen_seedance_video.provider import NotCreatedEvidence, classify_http

    for status in (400, 401, 403, 429, 500, 503):
        error = classify_http(status, phase="submit", api_id="seedance-video")
        assert isinstance(error, ProviderFailure) and not isinstance(error, NotCreatedEvidence)
    assert classify_http(503, phase="query", api_id="seedance-video").temporary
    assert classify_http(401, phase="query", api_id="seedance-video").scope == "all"


async def test_local_http_synthetic_adapter_submit_query_and_protection(setup, fake_http):
    import json

    from zhenzhen_seedance_video.network import NetworkPolicy, origin
    from zhenzhen_seedance_video.provider import classify_http
    from zhenzhen_seedance_video.provider_response import decode_response

    engine, admission, adapter, leases, clock = setup
    network = NetworkPolicy(engine.config, _test_origins=[origin(fake_http.url)])

    class HTTPAdapter(SyntheticAdapter):
        async def submit(self, row, payload):
            status, body = await network.request(
                "POST",
                fake_http.url + "/v1/video/generations",
                phase="submit",
                credential=True,
                json={"model": row["model"], "prompt": "synthetic"},
            )
            if status != 200:
                raise classify_http(status, phase="submit", api_id=row["api_id"])
            return decode_response(body, expected_model=row["model"])

        async def query(self, row):
            status, body = await network.request(
                "GET",
                fake_http.url + "/v1/video/generations/" + row["remote_id"],
                phase="query",
                credential=True,
            )
            if status != 200:
                raise classify_http(status, phase="query", api_id=row["api_id"])
            return decode_response(body, expected_model=row["model"], expected_id=row["remote_id"])

    engine.adapter = HTTPAdapter()
    task = await submit(admission, "http")
    payload = {
        "id": "synthetic-remote",
        "object": "video",
        "model": "seedance-2.0-mini-t2v",
        "status": "queued",
        "progress": 0,
        "created_at": 1783377182,
    }
    fake_http.responses.append((200, {}, json.dumps(payload).encode()))
    fake_http.responses.append((503, {}, b"synthetic temporary"))
    fake_http.responses.append((401, {}, b"synthetic auth failure"))
    try:
        await engine.dispatch()
        await engine.poll_due()
        clock.advance(3)
        await engine.poll_due()
        assert len([r for r in fake_http.requests if r[0] == "POST"]) == 1
        row = await engine._row(task["task_id"])
        assert row["auto_mode"] == "needs_attention" and row["remote_id"] == "synthetic-remote"
        assert await engine._blocked(row)
    finally:
        await network.close()


async def test_automatic_synthetic_runner(setup):
    engine, admission, adapter, leases, clock = setup
    task = await submit(admission, "runner")
    adapter.status = "completed"
    stop = asyncio.Event()
    completed = asyncio.Event()
    original_observe = engine.state.observe

    async def observe(*args, **kwargs):
        result = await original_observe(*args, **kwargs)
        if result["remote_state"] == "succeeded":
            completed.set()
        return result

    engine.state.observe = observe
    running = asyncio.create_task(engine.run(stop))
    try:
        await asyncio.wait_for(completed.wait(), 3)
    finally:
        stop.set()
        await running
    assert adapter.posts == [task["task_id"]]
    assert (await engine.state.get(task["task_id"]))["delivery"] == "pending"


async def test_failed_prepare_blocks_only_affected_api_and_keeps_sequence(setup):
    engine, admission, adapter, leases, clock = setup
    a = await submit(admission, "blocked")
    b = await submit(admission, "other-api", True)

    async def prepare(row):
        if row["api_id"] == "seedance-video":
            raise ProviderFailure("API_CONFIGURATION", scope="seedance-video")
        return {}

    adapter.prepare = prepare
    assert await engine.dispatch() == [b["task_id"]]
    assert (await engine._row(a["task_id"]))["sequence"] < (await engine._row(b["task_id"]))[
        "sequence"
    ]


async def test_resume_abandon_version_conflict_and_no_extra_round(setup):
    from zhenzhen_seedance_video.task_state import StateError

    engine, admission, adapter, leases, clock = setup
    task = await submit(admission, "race")
    await engine.dispatch()
    row = await engine._attention(task["task_id"], "QUERY_RETRIES_EXHAUSTED")
    resumed = await engine.resume(task["task_id"], expected_version=row["version"])
    with pytest.raises(StateError, match="VERSION_CONFLICT"):
        await engine.state.abandon(
            task["task_id"],
            expected_version=row["version"],
            reason="racing",
            confirmed=True,
            now="now",
        )
    assert await engine.resume(task["task_id"], expected_version=row["version"]) == resumed


async def test_before_send_failure_and_cancel_pending_success(setup, monkeypatch):
    engine, admission, adapter, leases, clock = setup
    task = await submit(admission, "before-send")
    original = engine.db.run_effect

    async def fail(*args, **kwargs):
        raise OSError("synthetic interruption before send")

    monkeypatch.setattr(engine.db, "run_effect", fail)
    await engine.dispatch()
    monkeypatch.setattr(engine.db, "run_effect", original)
    await engine.recover()
    assert not adapter.posts
    assert (await engine.state.get(task["task_id"]))["generation_slot_held"] == 1
    second = await submit(admission, "cancel-pending")
    await engine.dispatch()
    await engine.db.execute(
        lambda c: (
            c.execute(
                "UPDATE tasks SET cancel_requested=1 WHERE task_id=?", (second["task_id"],)
            ).rowcount
        )
    )
    adapter.status = "completed"
    await engine.poll_due()
    final = await engine.state.get(second["task_id"])
    assert final["remote_state"] == "succeeded" and final["delivery"] == "pending"


async def test_protection_rejects_new_admission_but_allows_find(setup):
    from zhenzhen_seedance_video.admission import AdmissionError

    engine, admission, adapter, leases, clock = setup
    accepted = await submit(admission, "known")
    await engine.protect("all")
    assert (await admission.find("known"))["task_id"] == accepted["task_id"]
    with pytest.raises(AdmissionError, match="API_PROTECTED"):
        await submit(admission, "new")


async def test_query_late_after_abandon_and_remote_cancel_unverified(setup):
    from zhenzhen_seedance_video.task_state import StateError

    engine, admission, adapter, leases, clock = setup
    task = await submit(admission, "late-query")
    await engine.dispatch()
    row = await engine.state.get(task["task_id"])
    with pytest.raises(StateError, match="REMOTE_CANCEL_CAPABILITY_UNVERIFIED"):
        await engine.state.cancel_unsubmitted(
            task["task_id"], expected_version=row["version"], now="now"
        )
    entered, release = asyncio.Event(), asyncio.Event()
    original = adapter.query

    async def delayed(row):
        entered.set()
        await release.wait()
        adapter.status = "completed"
        return await original(row)

    adapter.query = delayed
    querying = asyncio.create_task(engine.query(task["task_id"]))
    await entered.wait()
    await engine.state.abandon(
        task["task_id"], expected_version=row["version"], reason="stop", confirmed=True, now="now"
    )
    release.set()
    await querying
    final = await engine.state.get(task["task_id"])
    assert final["remote_state"] == "succeeded" and final["auto_mode"] == "abandoned"
    assert final["delivery"] == "none"


async def test_query_queue_rechecks_deadline_before_request(setup):
    engine, admission, adapter, leases, clock = setup
    engine.config = replace(
        engine.config, limits=dict(engine.config.limits) | {"TRACKING_TIMEOUT_SECONDS": 2}
    )
    engine._query_slots = asyncio.Semaphore(1)
    await submit(admission, "slow")
    b = await submit(admission, "queued-query")
    await engine.dispatch()
    original = adapter.query

    async def slow(row):
        clock.advance(3)
        return await original(row)

    adapter.query = slow
    await engine.poll_due()
    assert len(adapter.queries) == 1
    assert "TRACKING_TIMEOUT" in (await engine.state.get(b["task_id"]))["attention"]


async def test_restore_binding_requires_explicit_resume_and_preserves_history(setup):
    engine, admission, adapter, leases, clock = setup
    task = await submit(admission, "binding")
    await engine.dispatch()
    engine.binding = "different"
    await engine.recover()
    row = await engine.state.get(task["task_id"])
    assert row["auto_mode"] == "needs_attention"
    engine.binding = "binding"
    await engine.recover()
    assert (await engine.state.get(task["task_id"]))["auto_mode"] == "needs_attention"
    resumed = await engine.resume(task["task_id"], expected_version=row["version"])
    assert resumed["auto_mode"] == "active" and resumed["generation_slot_held"] == 1
    stored = await engine._row(task["task_id"])
    assert stored["tracking_round"] == 2


async def test_refresh_success_clears_query_diagnostics(setup):
    engine, admission, adapter, leases, clock = setup
    task = await submit(admission, "query-error")
    await engine.dispatch()
    await engine._attention(task["task_id"], "QUERY_RESPONSE_INVALID")
    adapter.status = "completed"
    refreshed = await engine.refresh(task["task_id"])
    assert refreshed["attention"] == [] and refreshed["delivery"] == "pending"
