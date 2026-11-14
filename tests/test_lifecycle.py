import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path

import pytest
from test_artifacts import video
from test_scheduler import SyntheticAdapter, submit

from zhenzhen_seedance_video.admission import AdmissionService
from zhenzhen_seedance_video.artifacts import ArtifactService
from zhenzhen_seedance_video.cleanup import CleanupService
from zhenzhen_seedance_video.config import load_configuration
from zhenzhen_seedance_video.leases import LeaseManager
from zhenzhen_seedance_video.lifecycle import Lifecycle
from zhenzhen_seedance_video.network import NetworkPolicy, origin
from zhenzhen_seedance_video.scheduler import Scheduler
from zhenzhen_seedance_video.storage import Database


@pytest.fixture
async def factory(monkeypatch, fake_http, clock):
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_API_KEY", "synthetic")
    config = load_configuration()
    adapter = SyntheticAdapter()

    async def references(row):
        return [{"url": fake_http.url + "/video"}]

    adapter.artifacts = references

    @asynccontextmanager
    async def open_services(*, binding="binding", limit=3, output=None):
        selected = replace(
            config,
            output_dir=output or config.output_dir,
            limits=dict(config.limits)
            | {"GENERATION_CONCURRENCY": limit, "SHUTDOWN_DRAIN_SECONDS": 0.1},
        )
        db = Database(selected.state_dir)
        net = NetworkPolicy(selected, _test_origins=[origin(fake_http.url)])
        admission = AdmissionService(db, selected, binding)
        artifacts = ArtifactService(db, selected, net, wall=lambda: clock.utc)
        cleanup = CleanupService(db, selected, wall=lambda: clock.utc)
        leases = LeaseManager(
            lease_seconds=30, grace_seconds=1, drain_seconds=0.1, clock=lambda: clock.monotonic
        )
        leases.join("host")
        scheduler = Scheduler(
            db,
            selected,
            binding,
            adapter,
            leases=leases,
            delivery=artifacts,
            wall=lambda: clock.utc,
            monotonic=lambda: clock.monotonic,
        )
        service = Lifecycle(admission, artifacts, cleanup, binding, leases, scheduler)
        try:
            yield service
        finally:
            await service.close()
            await artifacts.close()
            await cleanup.close()
            await net.close()
            await db.close()

    yield open_services, adapter, fake_http, clock


async def test_restart_rebuilds_capacity_preserves_budget_and_original_output(factory, tmp_path):
    open_services, adapter, http, clock = factory
    async with open_services() as old:
        await old.recover()
        a = await submit(old.admission, "a")
        b = await submit(old.admission, "b")
        await old.scheduler.dispatch()
        queued = await submit(old.admission, "queued")
        adapter.query_failure = True
        await old.scheduler.query(a["task_id"])
        row = await old.scheduler._row(a["task_id"])
        budget = await old.scheduler._budget(row)
        original_output = row["output_dir"]
        await old.db.execute(lambda c: c.execute("UPDATE tasks SET generation_slot_held=0"))
    async with open_services(limit=1, output=tmp_path / "new-output") as new:
        await new.recover()
        for task in (a, b):
            assert (await new.scheduler.state.get(task["task_id"]))["generation_slot_held"] == 1
        row = await new.scheduler._row(a["task_id"])
        assert await new.scheduler._budget(row) == budget
        assert row["output_dir"] == original_output
        assert await new.scheduler.dispatch() == []
        adapter.query_failure = False
        count = len(adapter.queries)
        await new.scheduler.poll_due()
        assert adapter.queries[count:] == [b["task_id"]]
        adapter.status = "completed"
        await new.scheduler.refresh(a["task_id"])
        await new.scheduler.refresh(b["task_id"])
        http.responses.extend([(200, {}, video()), (200, {}, video())])
        await new.scheduler.deliver_due()
        artifacts = await new.artifacts.list(a["task_id"])
        assert Path(artifacts["items"][0]["target_path"]).is_relative_to(Path(original_output))
        assert await new.scheduler.dispatch() == [queued["task_id"]]
        assert len(adapter.posts) == 3


async def test_restart_known_id_unknown_submission_stopped_and_identity(factory):
    open_services, adapter, _, _ = factory
    async with open_services() as old:
        await old.recover()
        known = await submit(old.admission, "known")
        unknown = await submit(old.admission, "unknown")
        await old.scheduler.dispatch()
        abandoned = await submit(old.admission, "abandoned")
        await old.scheduler.dispatch()
        row = await old.scheduler.state.get(abandoned["task_id"])
        await old.scheduler.state.abandon(
            abandoned["task_id"],
            expected_version=row["version"],
            reason="stop",
            confirmed=True,
            now="now",
        )
        await old.db.execute(
            lambda c: (
                c.execute(
                    "UPDATE tasks SET stage='submitting' WHERE task_id=?", (known["task_id"],)
                ),
                c.execute(
                    "UPDATE tasks SET stage='submitting',remote_id=NULL,remote_state='unknown' "
                    "WHERE task_id=?",
                    (unknown["task_id"],),
                ),
            )
        )
    async with open_services() as new:
        await new.recover()
        assert (await new.scheduler.state.get(known["task_id"]))["stage"] == "tracking"
        state = await new.scheduler.state.get(unknown["task_id"])
        assert state["auto_mode"] == "needs_attention" and state["generation_slot_held"] == 1
        assert (await new.scheduler.state.get(abandoned["task_id"]))["auto_mode"] == "abandoned"
        assert await new.scheduler.dispatch() == []
    async with open_services(binding="different") as new:
        await new.recover()
        state = await new.scheduler.state.get(known["task_id"])
        assert "CONNECTION_IDENTITY_UNVERIFIED" in state["attention"]
        assert state["generation_slot_held"] == 1
        await new.scheduler.poll_due()
        assert adapter.queries == []


async def test_drain_has_one_deadline_and_restart_never_resubmits(factory):
    open_services, adapter, _, clock = factory
    entered = asyncio.Event()

    async def blocked(row, payload):
        adapter.posts.append(row["task_id"])
        entered.set()
        await asyncio.Event().wait()

    adapter.submit = blocked
    async with open_services() as old:
        await old.recover()
        task = await submit(old.admission, "in-flight")
        runner = asyncio.create_task(old.run())
        await asyncio.wait_for(entered.wait(), 2)
        old.leases.drop("host")
        assert not old.leases.dispatch_allowed
        clock.advance(2)
        runner.cancel()
        await asyncio.gather(runner, return_exceptions=True)
        await asyncio.wait_for(old.close(), 1)
        assert old.idle
    async with open_services() as new:
        await new.recover()
        state = await new.scheduler.state.get(task["task_id"])
        assert state["remote_state"] == "unknown" and state["generation_slot_held"] == 1
        assert "SUBMISSION_UNKNOWN" in state["attention"]
        await new.scheduler.dispatch()
        assert len(adapter.posts) == 1


async def test_recovery_barrier_failure_never_starts_work(factory, monkeypatch):
    open_services, adapter, _, _ = factory
    async with open_services() as service:
        await submit(service.admission, "queued")

        async def fail():
            raise OSError("synthetic recovery failure")

        monkeypatch.setattr(service.artifacts, "recover", fail)
        with pytest.raises(OSError):
            await service.recover()
        with pytest.raises(RuntimeError, match="RECOVERY_REQUIRED"):
            await service.run()
        assert not service.ready and not adapter.posts


@pytest.mark.parametrize("point", ["download_before_publish", "download_after_publish"])
async def test_restart_publication_then_cleanup_keeps_original_and_budget(factory, tmp_path, point):
    open_services, adapter, http, _ = factory
    source = tmp_path / "input.png"
    source.write_bytes(b"synthetic input")
    async with open_services() as old:
        await old.recover()
        task = await old.admission.submit(
            "material",
            {
                "model": "seedance-2.0-mini-i2v",
                "prompt": "synthetic",
                "images": [{"local_path": str(source)}],
            },
        )
        identifier = task["task_id"]
        await old.scheduler.dispatch()
        adapter.status = "completed"
        await old.scheduler.refresh(identifier)
        artifact = (await old.artifacts.register(identifier, [{"url": http.url + "/video"}]))[0]

        def crash(current):
            if current == point:
                raise RuntimeError("synthetic-crash")

        old.artifacts.hook = crash
        http.responses.append((200, {}, video()))
        with pytest.raises(RuntimeError, match="synthetic-crash"):
            await old.artifacts.download(artifact)
    async with open_services() as new:
        await new.recover()
        if point == "download_before_publish":
            http.responses.append((200, {}, video()))
            await new.scheduler.deliver_due()
        state = await new.scheduler.state.get(identifier)
        assert state["delivery"] == "ready"
        await new.cleanup.due()
        assert (await new.scheduler.state.get(identifier))["cleanup_state"] == "done"
        assert source.read_bytes() == b"synthetic input"
        assert len(adapter.posts) == 1
        item = (await new.artifacts.list(identifier))["items"][0]
        assert await asyncio.to_thread(Path(item["target_path"]).read_bytes) == video()


async def test_restart_expired_tracking_and_exhausted_cleanup_are_not_reset(factory, tmp_path):
    open_services, adapter, _, clock = factory
    source = tmp_path / "input.png"
    source.write_bytes(b"input")
    async with open_services() as old:
        await old.recover()
        tracking = await submit(old.admission, "tracking")
        await old.scheduler.dispatch()
        cancelled = await old.admission.submit(
            "cleanup",
            {
                "model": "seedance-2.0-mini-i2v",
                "prompt": "synthetic",
                "images": [{"local_path": str(source)}],
            },
        )
        await old.scheduler.state.cancel_unsubmitted(
            cancelled["task_id"], expected_version=1, now="now"
        )
        await old.db.execute(
            lambda c: c.execute(
                "UPDATE cleanup_jobs SET state='failed',remaining_budget=0,"
                "next_attempt_at='2099-01-01T00:00:00+00:00'"
            )
        )
        clock.advance(30000)
    async with open_services() as new:
        await new.recover()
        state = await new.scheduler.state.get(tracking["task_id"])
        assert "TRACKING_TIMEOUT" in state["attention"] and state["generation_slot_held"] == 1
        before = await new.db.execute(
            lambda c: [
                tuple(r)
                for r in c.execute(
                    "SELECT state,remaining_budget,next_attempt_at FROM cleanup_jobs"
                )
            ],
            write=False,
        )
        await new.cleanup.due()
        after = await new.db.execute(
            lambda c: [
                tuple(r)
                for r in c.execute(
                    "SELECT state,remaining_budget,next_attempt_at FROM cleanup_jobs"
                )
            ],
            write=False,
        )
        assert before == after and before[0][1] == 0
        await new.scheduler.poll_due()
        assert not adapter.queries


async def test_preparing_recovery_keeps_fifo_and_grace_only_finishes_existing_query(factory):
    open_services, adapter, _, clock = factory
    async with open_services() as old:
        await old.recover()
        first = await submit(old.admission, "first")
        second = await submit(old.admission, "second")
        await old.db.execute(
            lambda c: c.execute(
                "UPDATE tasks SET stage='preparing' WHERE task_id=?", (first["task_id"],)
            )
        )
    async with open_services(limit=1) as new:
        await new.recover()
        assert await new.scheduler.dispatch() == [first["task_id"]]
        entered, release = asyncio.Event(), asyncio.Event()
        original = adapter.query

        async def delayed(row):
            entered.set()
            await release.wait()
            return await original(row)

        adapter.query = delayed
        query = asyncio.create_task(new.scheduler.refresh(first["task_id"]))
        await asyncio.wait_for(entered.wait(), 1)
        new.leases.drop("host")
        assert new.leases.network_allowed and not new.leases.dispatch_allowed
        assert await new.scheduler.dispatch() == []
        clock.advance(1.01)
        assert not new.leases.network_allowed
        adapter.status = "completed"
        release.set()
        await query
        assert (await new.scheduler.state.get(first["task_id"]))["remote_state"] == "succeeded"
        await new.scheduler.deliver_due()
        assert not (await new.artifacts.list(first["task_id"]))["items"]
        assert adapter.posts == [first["task_id"]]
        assert (await new.scheduler.state.get(second["task_id"]))["stage"] == "queued"


@pytest.mark.parametrize(
    "mode,extra,binding,expected",
    [
        ("active", "", "binding", "active"),
        ("needs_attention", "", "binding", "needs_attention"),
        ("abandoned", "", "binding", "abandoned"),
        ("active", "ARTIFACT_RETRIES_EXHAUSTED", "binding", "needs_attention"),
        ("active", "", "different", "needs_attention"),
    ],
)
async def test_partial_collection_recovery_preserves_execution_authority(
    factory, mode, extra, binding, expected
):
    import json

    open_services, _, _, _ = factory
    reasons = ["ARTIFACT_SET_UNVERIFIED"] + ([extra] if extra else [])
    async with open_services() as old:
        await old.recover()
        tid = (await submit(old.admission, "partial"))["task_id"]
        await old.db.execute(
            lambda c: c.execute(
                "UPDATE tasks SET remote_state='succeeded',stage='downloading',"
                "delivery='pending',auto_mode=?,attention=? WHERE task_id=?",
                (mode, json.dumps(reasons), tid),
            )
        )
    async with open_services(binding=binding) as new:
        await new.recover()
        row = await new.scheduler.state.get(tid)
        assert row["auto_mode"] == expected
        assert "ARTIFACT_SET_UNVERIFIED" in row["attention"]
        if extra:
            assert extra in row["attention"]
        if binding != "binding":
            assert "CONNECTION_IDENTITY_UNVERIFIED" in row["attention"]
