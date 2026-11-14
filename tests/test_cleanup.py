import asyncio
import threading
from pathlib import Path

import pytest

from zhenzhen_seedance_video.admission import AdmissionService
from zhenzhen_seedance_video.cleanup import CleanupService
from zhenzhen_seedance_video.config import load_configuration
from zhenzhen_seedance_video.materials import locked_source
from zhenzhen_seedance_video.storage import Database, StorageError
from zhenzhen_seedance_video.task_state import TaskState, _change, _load


@pytest.fixture
async def cleanup(monkeypatch, tmp_path, clock):
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_API_KEY", "synthetic")
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_CLEANUP_RETRIES", "1")
    config = load_configuration()
    db = Database(config.state_dir)
    admission = AdmissionService(db, config, "binding")
    original = tmp_path / "original.png"
    await asyncio.to_thread(original.write_bytes, b"synthetic-original")
    result = await admission.submit(
        "request",
        {
            "model": "seedance-2.0-mini-i2v",
            "prompt": "test",
            "images": [{"local_path": str(original)}],
        },
    )
    task_id = result["task_id"]
    material = await db.execute(
        lambda c: dict(c.execute("SELECT * FROM material_copies").fetchone()), write=False
    )
    service = CleanupService(db, config, wall=lambda: clock.utc)
    try:
        yield service, admission, task_id, material, original, clock
    finally:
        await service.close()
        await admission.close()
        await service.db.close()


async def transition(service, task_id, **updates):
    await service.db.execute(
        lambda c: _change(c, _load(c, task_id), updates, kind="synthetic_fact", now="now")
    )


async def jobs(service):
    return await service.db.execute(
        lambda c: [dict(r) for r in c.execute("SELECT * FROM cleanup_jobs")], write=False
    )


@pytest.mark.parametrize(
    "updates",
    [
        {"remote_state": "succeeded", "delivery": "ready"},
        {"remote_state": "failed"},
        {"remote_state": "cancelled"},
        {"locally_cancelled": 1},
        {"auto_mode": "abandoned", "remote_state": "unknown"},
        {"auto_mode": "abandoned", "remote_state": "succeeded", "delivery": "partial"},
    ],
)
async def test_terminal_triggers_persist_then_delete_only_copy(cleanup, updates):
    service, _, task_id, material, original, _ = cleanup
    await transition(service, task_id, **updates)
    assert len(await jobs(service)) == 1
    await service.due()
    assert (await jobs(service))[0]["state"] == "done"
    assert not await asyncio.to_thread(Path(material["managed_path"]).exists)
    assert await asyncio.to_thread(original.read_bytes) == b"synthetic-original"
    state = await TaskState(service.db).get(task_id)
    for key, value in updates.items():
        assert state[key] == value
    assert state["cleanup_state"] == "done"
    await service.due()
    assert len(await jobs(service)) == 1


@pytest.mark.parametrize(
    "updates",
    [
        {"remote_state": "unknown"},
        {"remote_state": "running"},
        {"remote_state": "succeeded", "delivery": "pending"},
        {"remote_state": "succeeded", "delivery": "partial", "auto_mode": "needs_attention"},
    ],
)
async def test_unfinished_and_unknown_retained(cleanup, updates):
    service, _, task_id, material, _, _ = cleanup
    await transition(service, task_id, **updates)
    await service.due()
    assert not await jobs(service)
    assert await asyncio.to_thread(Path(material["managed_path"]).exists)
    with pytest.raises(RuntimeError, match="NOT_AUTHORIZED"):
        await service.retry(task_id, expected_version=1)


async def test_open_file_budget_persists_and_explicit_retry(cleanup):
    service, _, task_id, material, _, clock = cleanup
    await transition(service, task_id, locally_cancelled=1)
    with locked_source(material["managed_path"]):
        await service.due()
        first = (await jobs(service))[0]
        assert first["remaining_budget"] == 1 and first["state"] == "pending"
        await service.due()
        assert (await jobs(service))[0] == first
        clock.advance(90)
        await service.due()
        assert (await jobs(service))[0]["state"] == "failed"
    await service.db.close()
    service.db = Database(service.config.state_dir)
    service.readers.db = service.db
    await service.due()
    assert (await jobs(service))[0]["remaining_budget"] == 0
    state = await TaskState(service.db).get(task_id)
    with pytest.raises(RuntimeError, match="VERSION_CONFLICT"):
        await service.retry(task_id, expected_version=state["version"] - 1)
    await service.retry(task_id, expected_version=state["version"])
    await service.due()
    assert (await jobs(service))[0]["state"] == "done"
    assert "MATERIAL_CLEANUP_FAILED" not in (await TaskState(service.db).get(task_id))["attention"]


async def test_delete_then_persist_failure_reconciles_absence(cleanup):
    service, _, task_id, material, _, _ = cleanup
    await transition(service, task_id, auto_mode="abandoned")

    def fail(point):
        if point == "cleanup_after_delete":
            raise StorageError("STORAGE_FAULT")

    service.hook = fail
    with pytest.raises(StorageError):
        await service.due()
    assert (await jobs(service))[0]["state"] == "deleting"
    assert not await asyncio.to_thread(Path(material["managed_path"]).exists)
    service.hook = lambda _: None
    await service.due()
    assert (await jobs(service))[0]["state"] == "done"


async def test_missing_file_is_success(cleanup):
    service, _, task_id, material, _, _ = cleanup
    await asyncio.to_thread(Path(material["managed_path"]).unlink)
    await transition(service, task_id, remote_state="failed")
    await service.due()
    assert (await jobs(service))[0]["state"] == "done"


@pytest.mark.parametrize("attack", ["outside", "symlink", "changed"])
async def test_ownership_link_and_changed_content_rejected(cleanup, attack):
    service, _, task_id, material, original, clock = cleanup
    path = Path(material["managed_path"])
    if attack == "outside":
        await service.db.execute(
            lambda c: c.execute("UPDATE material_copies SET managed_path=?", (str(original),))
        )
    elif attack == "changed":
        await asyncio.to_thread(path.write_bytes, b"foreign")
    else:
        await asyncio.to_thread(path.unlink)
        await asyncio.to_thread(path.symlink_to, original)
    try:
        await transition(service, task_id, remote_state="failed")
        await service.due()
        clock.advance(90)
        await service.due()
        assert (await jobs(service))[0]["state"] == "failed"
        assert await asyncio.to_thread(original.read_bytes) == b"synthetic-original"
    finally:
        if attack == "symlink":
            await asyncio.to_thread(path.unlink)


async def test_read_thread_stops_and_handle_closes_before_delete(cleanup):
    service, _, task_id, material, _, _ = cleanup
    entered, closed = threading.Event(), threading.Event()

    async def reader():
        async with service.readers.use(task_id) as stop:

            def read():
                try:
                    with locked_source(material["managed_path"]):
                        entered.set()
                        stop.wait(3)
                finally:
                    closed.set()

            await service.readers.thread(read)

    work = asyncio.create_task(reader())
    assert await asyncio.to_thread(entered.wait, 3)
    await transition(service, task_id, auto_mode="abandoned")
    service.hook = lambda point: (
        closed.is_set() or (_ for _ in ()).throw(AssertionError("reader open"))
    )
    await service.due()
    await asyncio.gather(work, return_exceptions=True)
    assert closed.is_set() and (await jobs(service))[0]["state"] == "done"
    with pytest.raises(RuntimeError, match="CLEANUP_PENDING"):
        async with service.readers.use(task_id):
            pytest.fail("new reader admitted")


async def test_intent_storage_failure_never_deletes(cleanup):
    service, _, task_id, material, _, _ = cleanup
    await transition(service, task_id, remote_state="failed")
    original = service.db.execute

    async def fail(*args, **kwargs):
        raise StorageError("STORAGE_FAULT")

    service.db.execute = fail
    with pytest.raises(StorageError):
        await service.due()
    service.db.execute = original
    assert await asyncio.to_thread(Path(material["managed_path"]).exists)


async def test_abandon_stops_inflight_repair_without_recreating_copy(cleanup, monkeypatch):
    import zhenzhen_seedance_video.admission as admission_module

    service, admission, task_id, material, original, _ = cleanup
    entered, ended = threading.Event(), threading.Event()
    receive = admission_module.receive

    def slow(*args, **kwargs):
        entered.set()
        try:
            kwargs["stop"].wait(3)
            return receive(*args, **kwargs)
        finally:
            ended.set()

    monkeypatch.setattr(admission_module, "receive", slow)
    state = await TaskState(service.db).get(task_id)
    repair = asyncio.create_task(
        admission.repair(
            task_id, material["material_id"], str(original), expected_version=state["version"]
        )
    )
    assert await asyncio.to_thread(entered.wait, 3)
    state = await TaskState(service.db).get(task_id)
    await TaskState(service.db).abandon(
        task_id, expected_version=state["version"], reason="stop", confirmed=True, now="now"
    )
    await service.due()
    await asyncio.gather(repair, return_exceptions=True)
    assert ended.is_set()
    assert (await jobs(service))[0]["state"] == "done"
    assert not await asyncio.to_thread(Path(material["managed_path"]).exists)


async def test_budget_zero_interrupted_delete_only_reconciles_absence(cleanup):
    service, _, task_id, material, _, _ = cleanup
    await transition(service, task_id, remote_state="failed")
    await service.db.execute(
        lambda c: c.execute("UPDATE cleanup_jobs SET state='deleting',remaining_budget=0")
    )
    await service.due()
    assert (await jobs(service))[0]["state"] == "failed"
    assert await asyncio.to_thread(Path(material["managed_path"]).exists)


async def test_cleanup_preserves_generated_source_used_for_upscale(cleanup):
    service, admission, _, _, original, _ = cleanup
    source = original.with_suffix(".mp4")
    await asyncio.to_thread(source.write_bytes, b"synthetic-generated-video")
    response = await admission.submit(
        "upscale",
        {
            "model": "zhenzhen-upscaler",
            "metadata": {
                "content": [
                    {"type": "video_url", "video_url": {"url": {"local_path": str(source)}}}
                ]
            },
        },
        api_id="zhenzhen-upscaler",
    )
    await transition(service, response["task_id"], remote_state="succeeded", delivery="ready")
    await service.due()
    assert await asyncio.to_thread(source.read_bytes) == b"synthetic-generated-video"
    assert (await TaskState(service.db).get(response["task_id"]))["cleanup_state"] == "done"


async def test_nested_read_scopes_remain_registered(cleanup):
    service, _, task_id, _, _, _ = cleanup
    async with service.readers.use(task_id):
        async with service.readers.use(task_id):
            assert len(service.readers.active[task_id][asyncio.current_task()]) == 2
        assert len(service.readers.active[task_id][asyncio.current_task()]) == 1
    assert task_id not in service.readers.active
