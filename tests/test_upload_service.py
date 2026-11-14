import asyncio
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_scheduler import SyntheticAdapter

from zhenzhen_seedance_video.admission import AdmissionService
from zhenzhen_seedance_video.cleanup import CleanupService
from zhenzhen_seedance_video.config import load_configuration
from zhenzhen_seedance_video.provider import ProviderFailure
from zhenzhen_seedance_video.scheduler import Scheduler
from zhenzhen_seedance_video.storage import Database
from zhenzhen_seedance_video.task_state import _change, _load
from zhenzhen_seedance_video.upload_service import UploadService
from zhenzhen_seedance_video.uploads import UploadedReference


class Sender:
    def __init__(self):
        self.calls = 0
        self.fail = False
        self.expiry = 20
        self.started = asyncio.Event()
        self.block = None
        self.stream = None

    async def __call__(self, network, stream, **kwargs):
        self.calls += 1
        self.stream = stream
        self.started.set()
        if self.block:
            await self.block.wait()
        assert hashlib.sha256(stream.read()).hexdigest() == kwargs["expected_sha256"]
        assert kwargs["suffix"] == ".png"
        if self.fail:
            raise ProviderFailure("TEMPORARY_UPLOAD", temporary=True)
        return UploadedReference(
            f"https://cdn.example.com/{self.calls}?secret=signed",
            "image",
            kwargs["expected_size"],
            self.expiry,
        )


class Adapter(SyntheticAdapter):
    async def prepare(self, row):
        return json.loads(row["effective_parameters"])

    async def submit(self, row, payload):
        assert payload["images"][0].startswith("https://cdn.example.com/")
        return await super().submit(row, payload)


@pytest.fixture
async def setup(monkeypatch, tmp_path, clock):
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_API_KEY", "synthetic")
    config = load_configuration()
    config = replace(config, limits=dict(config.limits) | {"UPLOAD_RETRIES": 1})
    db = Database(config.state_dir)
    admission = AdmissionService(db, config, "binding")
    source = tmp_path / "original.png"
    source.write_bytes(b"synthetic image")
    task = await admission.submit(
        "upload",
        {
            "model": "seedance-2.0-mini-i2v",
            "prompt": "fox",
            "images": [{"local_path": str(source)}],
        },
    )
    sender = Sender()
    uploads = UploadService(db, config, "binding", None, send=sender, wall=lambda: clock.utc)
    adapter = Adapter()
    leases = SimpleNamespace(dispatch_allowed=True, network_allowed=True)
    scheduler = Scheduler(
        db,
        config,
        "binding",
        adapter,
        leases=leases,
        uploads=uploads,
        wall=lambda: clock.utc,
        monotonic=lambda: clock.monotonic,
    )
    try:
        yield scheduler, admission, uploads, sender, adapter, task["task_id"], clock, source
    finally:
        await scheduler.close()
        await admission.close()
        await db.close()


async def row(engine, tid):
    return await engine._row(tid)


async def records(db):
    return await db.execute(
        lambda c: [dict(r) for r in c.execute("SELECT * FROM uploads")], write=False
    )


async def test_scheduler_payload_identity_and_unknown_never_reupload(setup):
    engine, _, uploads, sender, adapter, tid, clock, source = setup
    before = await row(engine, tid)
    adapter.submit_failure = True
    assert await engine.dispatch() == [tid]
    after = await row(engine, tid)
    assert sender.calls == 1 and len(adapter.posts) == 1
    assert before["effective_parameters"] == after["effective_parameters"]
    assert before["intent_digest"] == after["intent_digest"]
    assert after["remote_state"] == "unknown"
    clock.advance(100)
    await engine.recover()
    assert await engine.dispatch() == []
    assert sender.calls == 1 and len(adapter.posts) == 1 and source.exists()


async def test_retry_budget_and_backoff_survive_new_service(setup):
    engine, _, uploads, sender, adapter, tid, clock, _ = setup
    sender.fail = True
    assert await engine.dispatch() == []
    assert sender.calls == 1 and not adapter.posts
    engine.uploads = UploadService(
        engine.db, engine.config, "binding", None, send=sender, wall=lambda: clock.utc
    )
    await engine.recover()
    await engine.dispatch()
    assert sender.calls == 1
    clock.advance(2)
    await engine.dispatch()
    assert sender.calls == 2
    assert (await row(engine, tid))["auto_mode"] == "needs_attention"
    assert (await records(engine.db))[0]["remaining_budget"] == 0
    clock.advance(100)
    await engine.recover()
    await engine.dispatch()
    assert sender.calls == 2 and not adapter.posts


async def test_expired_same_copy_reupload_and_generation_guard(setup):
    engine, _, uploads, sender, adapter, tid, clock, _ = setup
    before = await row(engine, tid)
    payload = await uploads.prepare(before)
    assert sender.calls == 1
    clock.advance(21)
    # The guard refuses a stale prepared payload in the generation intent transaction.
    from zhenzhen_seedance_video.task_state import StateError

    with pytest.raises(StateError, match="UPLOAD_REFERENCE_NOT_READY"):
        await engine.state.begin_submission(
            tid,
            expected_version=(await row(engine, tid))["version"],
            connection_binding="binding",
            limit=2,
            now="now",
            deadline=None,
            preparation_guard=uploads.guard,
        )
    assert (await row(engine, tid))["remote_state"] == "not_submitted"
    assert await engine.dispatch() == [tid]
    assert sender.calls == 2 and len(adapter.posts) == 1
    assert payload["images"][0] != (await records(engine.db))[0]["url"]
    assert before["effective_parameters"] == (await row(engine, tid))["effective_parameters"]


async def test_crash_intent_consumed_before_send_and_reopened_database(setup):
    engine, _, uploads, sender, adapter, tid, clock, _ = setup
    sender.block = asyncio.Event()
    operation = asyncio.create_task(uploads.prepare(await row(engine, tid)))
    await sender.started.wait()
    operation.cancel()
    with pytest.raises(asyncio.CancelledError):
        await operation
    assert sender.stream.closed
    assert (await records(engine.db))[0]["remaining_budget"] == 1
    # Actual SQLite close/open, not just an in-memory retry counter.
    await engine.db.close()
    reopened = Database(engine.config.state_dir)
    restarted = UploadService(
        reopened, engine.config, "binding", None, send=sender, wall=lambda: clock.utc
    )
    try:
        await restarted.recover()
        assert (await records(reopened))[0]["remaining_budget"] == 1
        assert (
            await restarted.prepare(await reopened.execute(lambda c: _load(c, tid), write=False))
            is None
        )
        sender.block = None
        clock.advance(2)
        assert await restarted.prepare(await reopened.execute(lambda c: _load(c, tid), write=False))
        assert sender.calls == 2 and not adapter.posts
        assert (await records(reopened))[0]["remaining_budget"] == 0
    finally:
        await reopened.close()


async def test_cleanup_cancels_upload_then_removes_only_copy(setup):
    engine, _, uploads, sender, adapter, tid, clock, source = setup
    sender.block = asyncio.Event()
    operation = asyncio.create_task(engine.dispatch())
    await sender.started.wait()
    await engine.db.execute(
        lambda c: _change(
            c, _load(c, tid), {"auto_mode": "abandoned", "epoch": 1}, kind="test_abandon", now="now"
        )
    )
    cleanup = CleanupService(engine.db, engine.config, wall=lambda: clock.utc)
    try:
        await cleanup.due()
        await operation
        assert sender.stream.closed and source.exists() and not adapter.posts
        assert (await row(engine, tid))["cleanup_state"] == "done"
        material = await engine.db.execute(
            lambda c: dict(c.execute("SELECT * FROM material_copies").fetchone()), write=False
        )
        assert not await asyncio.to_thread(Path(material["managed_path"]).exists)
    finally:
        await cleanup.close()


async def test_unknown_expiry_and_clock_rollback_require_attention(setup):
    engine, _, uploads, sender, adapter, tid, clock, _ = setup
    sender.expiry = None
    await engine.dispatch()
    assert (await row(engine, tid))["auto_mode"] == "needs_attention"
    assert not adapter.posts


async def test_duplicate_prepare_single_upload_and_cached_reference(setup):
    engine, _, uploads, sender, _, tid, _, _ = setup
    task = await row(engine, tid)
    a, b = await asyncio.gather(uploads.prepare(task), uploads.prepare(task))
    assert a == b and sender.calls == 1


async def test_clock_rollback_does_not_extend_reuse(setup):
    engine, _, uploads, sender, adapter, tid, clock, _ = setup
    await uploads.prepare(await row(engine, tid))
    clock.advance(-5)
    await engine.dispatch()
    assert sender.calls == 1 and not adapter.posts
    assert "UPLOAD_CLOCK_ROLLBACK" in (await row(engine, tid))["attention"]


async def test_permanent_failure_not_retried_and_auth_protects_dispatch(setup):
    engine, _, uploads, sender, adapter, tid, clock, _ = setup

    async def denied(*args, **kwargs):
        sender.calls += 1
        raise ProviderFailure("AUTH", scope="all")

    uploads.send = denied
    await engine.dispatch()
    clock.advance(100)
    await engine.dispatch()
    assert sender.calls == 1 and not adapter.posts
    assert await engine._blocked(await row(engine, tid))
    assert (await records(engine.db))[0]["state"] == "rejected"


async def test_host_departure_during_upload_prevents_generation(setup):
    engine, _, uploads, sender, adapter, tid, _, _ = setup
    sender.block = asyncio.Event()
    operation = asyncio.create_task(engine.dispatch())
    await sender.started.wait()
    engine.leases.dispatch_allowed = False
    sender.block.set()
    assert await operation == []
    assert not adapter.posts
    engine.leases.dispatch_allowed = True
    assert await engine.dispatch() == [tid]
    assert sender.calls == 1


async def test_storage_fault_never_starts_upload(setup):
    engine, _, uploads, sender, adapter, tid, _, _ = setup
    engine.db._fault.set()
    assert await engine.dispatch() == []
    assert sender.calls == 0 and not adapter.posts
    engine.db._fault.clear()


async def test_late_response_after_abandon_does_not_resume(setup):
    engine, _, uploads, sender, adapter, tid, _, _ = setup
    sender.block = asyncio.Event()
    operation = asyncio.create_task(engine.dispatch())
    await sender.started.wait()
    await engine.db.execute(
        lambda c: _change(
            c, _load(c, tid), {"auto_mode": "abandoned", "epoch": 1}, kind="test_abandon", now="now"
        )
    )
    sender.block.set()
    assert await operation == []
    assert not adapter.posts and (await records(engine.db))[0]["state"] == "discarded"


async def test_real_upload_component_with_synthetic_http_and_persistent_retry(setup):
    import httpx2

    from zhenzhen_seedance_video.models import BASE_URL
    from zhenzhen_seedance_video.network import NetworkPolicy, origin
    from zhenzhen_seedance_video.uploads import upload_once

    engine, _, uploads, _, adapter, tid, clock, source = setup
    requests = []

    async def respond(request):
        requests.append(request)
        assert request.url.path == "/v1/files/upload"
        assert b'filename="material.png"' in await request.aread()
        if len(requests) == 1:
            return httpx2.Response(429, json={"error": "synthetic"})
        return httpx2.Response(
            200,
            json={
                "url": "https://cdn.example.com/file.png",
                "size": 15,
                "file_type": "image",
                "expires_in": 30,
            },
        )

    network = NetworkPolicy(
        engine.config, _test_origins=[origin(BASE_URL)], _transport=httpx2.MockTransport(respond)
    )
    uploads.network, uploads.send = network, upload_once
    await asyncio.to_thread(source.unlink)
    try:
        assert await engine.dispatch() == []
        assert not adapter.posts
        clock.advance(2)
        assert await engine.dispatch() == [tid]
        assert len(requests) == 2 and len(adapter.posts) == 1
        assert (await records(engine.db))[0]["remaining_budget"] == 0
    finally:
        await network.close()


async def test_backoff_does_not_block_other_eligible_task(setup):
    engine, admission, uploads, sender, adapter, tid, clock, _ = setup
    sender.fail = True
    engine.config = replace(
        engine.config, limits=dict(engine.config.limits) | {"GENERATION_CONCURRENCY": 1}
    )
    await engine.dispatch()
    other = await admission.submit("other", {"model": "seedance-2.0-mini-t2v", "prompt": "fox"})

    # No local materials on this task; its adapter payload has no image requirement.
    async def submit_other(row, payload):
        return await SyntheticAdapter.submit(adapter, row, payload)

    adapter.submit = submit_other
    assert await engine.dispatch() == [other["task_id"]]
    assert sender.calls == 1 and adapter.posts == [other["task_id"]]
    assert (await row(engine, tid))["remote_state"] == "not_submitted"
