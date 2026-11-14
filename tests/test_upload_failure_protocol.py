"""Upload failure/expiry/cleanup across real MCP processes, synthetic HTTP only."""

import asyncio
from pathlib import Path

import pytest
from test_main_video_protocol import WORKER, delivered, wait_state
from test_material_protocol import ORIGINAL, counts, persisted
from test_tools import call, protocol
from test_windows_integration import backend as backend
from test_windows_integration import until


async def submit_local(session, source):
    await asyncio.to_thread(source.write_bytes, ORIGINAL)
    return await call(
        session,
        "submit_video",
        request_key="upload-fault",
        request={
            "model": "seedance-2.0-mini-i2v",
            "prompt": "fox",
            "images": [{"local_path": str(source)}],
        },
    )


@pytest.mark.parametrize("exhaust", [False, True])
async def test_upload_retry_budget_and_restart(backend, tmp_path, monkeypatch, exhaust):
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_UPLOAD_RETRIES", "1")
    start, control, _, config = backend
    phase = "material-exhaust" if exhaust else "material-retry"
    (control / "release-upload").touch()
    (control / "complete").touch()
    child = await start(phase, worker=WORKER)
    async with protocol() as a:
        tid = (await submit_local(a, tmp_path / "source.png"))["task_id"]
        if exhaust:
            await wait_state(a, tid, lambda r: "UPLOAD_RETRIES_EXHAUSTED" in r["attention"])
        else:
            await delivered(a, tid, tmp_path / "first.mp4")
    await asyncio.to_thread(child.wait, timeout=12)
    before = await asyncio.to_thread(persisted, config)
    assert counts(control)["upload"] == 2
    assert before["uploads"][0]["remaining_budget"] == 0
    assert counts(control)["submit"] == (0 if exhaust else 1)
    restarted = await start("material-tracking", worker=WORKER)
    async with protocol() as b:
        found = await call(b, "find_task_by_request_key", request_key="upload-fault")
        assert found["task_id"] == tid
        if exhaust:
            row = await call(b, "get_task", task_id=tid)
            assert row["auto_mode"] == "needs_attention"
            assert row["remote_state"] == "not_submitted"
            await call(
                b, "wait_task", task_id=tid, after_version=row["version"], timeout_seconds=0.3
            )
            assert counts(control)["submit"] == 0
        else:
            await delivered(b, tid, tmp_path / "second.mp4")
        assert counts(control)["upload"] == 2
    await asyncio.to_thread(restarted.wait, timeout=12)
    after = await asyncio.to_thread(persisted, config)
    assert after["uploads"][0]["remaining_budget"] == 0
    assert not after["cleanup_jobs"]
    assert await asyncio.to_thread(Path(after["material_copies"][0]["managed_path"]).exists)


async def test_expired_uploaded_reference_reuploads_same_copy_after_restart(backend, tmp_path):
    start, control, _, config = backend
    (control / "release-upload").touch()
    child = await start("material-expiry", worker=WORKER)
    source = tmp_path / "source.png"
    async with protocol() as a:
        tid = (await submit_local(a, source))["task_id"]
        await until(lambda: child.poll() is not None)
        assert child.returncode == 91
    before = await asyncio.to_thread(persisted, config)
    assert counts(control)["submit"] == 0
    # Expiry is a synthetic one-second response value, not a supplier lifetime claim.
    await asyncio.sleep(1.1)
    await asyncio.to_thread(source.unlink)
    (control / "complete").touch()
    restarted = await start("material-expiry", worker=WORKER)
    async with protocol() as b:
        assert (await call(b, "find_task_by_request_key", request_key="upload-fault"))[
            "task_id"
        ] == tid
        await delivered(b, tid, tmp_path / "expired-recovered.mp4")
    await asyncio.to_thread(restarted.wait, timeout=12)
    after = await asyncio.to_thread(persisted, config)
    assert counts(control)["upload"] == 2 and counts(control)["submit"] == 1
    assert after["uploads"][0]["remaining_budget"] == before["uploads"][0]["remaining_budget"] - 1
    assert after["material_copies"][0]["sha256"] == before["material_copies"][0]["sha256"]
    assert after["tasks"][0]["effective_parameters"] == before["tasks"][0]["effective_parameters"]


async def test_abandon_inflight_upload_cleans_copy_and_stays_abandoned_after_restart(
    backend, tmp_path
):
    start, control, _, config = backend
    source = tmp_path / "source.png"
    child = await start("material-cleanup", worker=WORKER)
    async with protocol() as a, protocol() as b:
        tid = (await submit_local(a, source))["task_id"]
        await until(lambda: (control / "upload-entered").exists())
        row = await call(b, "get_task", task_id=tid)
        result = await call(
            b,
            "abandon_task",
            task_id=tid,
            expected_version=row["version"],
            reason="synthetic cleanup",
            acknowledge_remote_may_continue=True,
        )
        assert result.get("ok", True)
        await wait_state(b, tid, lambda r: r["cleanup_state"] == "done")
        assert counts(control)["submit"] == 0
        assert await asyncio.to_thread(source.read_bytes) == ORIGINAL
    await asyncio.to_thread(child.wait, timeout=12)
    before = await asyncio.to_thread(persisted, config)
    assert not await asyncio.to_thread(Path(before["material_copies"][0]["managed_path"]).exists)
    (control / "release-upload").touch()
    restarted = await start("material-cleanup", worker=WORKER)
    async with protocol() as c:
        row = await call(c, "get_task", task_id=tid)
        assert row["auto_mode"] == "abandoned" and row["cleanup_state"] == "done"
        assert counts(control)["upload"] == 1 and counts(control)["submit"] == 0
    await asyncio.to_thread(restarted.wait, timeout=12)
    assert child.returncode == restarted.returncode == 0
