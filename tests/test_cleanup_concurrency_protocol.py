"""Concurrent MCP cleanup retries grant one budget, including across backend restarts."""

import asyncio
from pathlib import Path

import pytest
from test_main_video_protocol import WORKER, wait_state
from test_material_protocol import counts, persisted
from test_mixed_cleanup_protocol import deletions
from test_mixed_lifecycle_protocol import submit_mixed
from test_multi_material_protocol import material_counts
from test_tools import call, protocol
from test_windows_integration import backend as backend
from test_windows_integration import until


@pytest.mark.parametrize("action", ["cancel_task", "abandon_task"])
async def test_concurrent_cleanup_retry_versions_restart(backend, tmp_path, monkeypatch, action):
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_CLEANUP_RETRIES", "1")
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_CLEANUP_CONCURRENCY", "1")
    start, control, _, config = backend
    phase = "material-multi-cleanup-exhaust-concurrent-mixed-video"
    (control / "release-upload").touch()
    child = await start(phase, worker=WORKER)
    async with protocol() as a, protocol() as b:
        tid, sources = await submit_mixed(a, tmp_path)
        await until(lambda: (control / "second-inflight").exists())
        row = await call(b, "get_task", task_id=tid)
        args = {"task_id": tid, "expected_version": row["version"]}
        if action == "abandon_task":
            args.update(reason="synthetic concurrent retry", acknowledge_remote_may_continue=True)
        assert (await call(b, action, **args)).get("ok", True)
        failed = await wait_state(a, tid, lambda r: r["cleanup_state"] == "failed")
        assert (await call(b, "get_task", task_id=tid))["version"] == failed["version"]
        (control / "pause-cleanup").touch()
    await asyncio.to_thread(child.wait, timeout=12)
    before = await asyncio.to_thread(persisted, config)
    assert deletions(control) == [1, 2, 1]
    failed_job = next(j for j in before["cleanup_jobs"] if j["state"] == "failed")
    assert failed_job["remaining_budget"] == 0
    (control / "release-cleanup").touch()
    second = await start(phase, worker=WORKER)
    async with protocol() as c, protocol() as d:
        found = await call(c, "find_task_by_request_key", request_key="mixed-lifecycle")
        assert found["task_id"] == tid and found["version"] == failed["version"]
        stale = await asyncio.gather(
            *[
                call(
                    session,
                    "retry_material_cleanup",
                    task_id=tid,
                    expected_version=found["version"] - 1,
                )
                for session in (c, d)
            ]
        )
        assert all(r["error"] == "VERSION_CONFLICT" for r in stale)
        assert deletions(control) == [1, 2, 1]
        results = await asyncio.gather(
            *[
                call(
                    session,
                    "retry_material_cleanup",
                    task_id=tid,
                    expected_version=found["version"],
                )
                for session in (c, d)
            ]
        )
        assert all(r.get("ok", True) for r in results)
        assert results[0] == results[1]
        assert results[0]["version"] == found["version"] + 1
        assert results[0]["cleanup_state"] == "pending"
    await asyncio.to_thread(second.wait, timeout=12)
    pending = await asyncio.to_thread(persisted, config)
    job = next(j for j in pending["cleanup_jobs"] if j["cleanup_id"] == failed_job["cleanup_id"])
    assert job["remaining_budget"] == 2 and job["state"] == "pending"
    assert deletions(control) == [1, 2, 1]
    third = await start(phase, worker=WORKER)
    async with protocol() as e, protocol() as f:
        row = await call(e, "get_task", task_id=tid)
        assert row["version"] == results[0]["version"]
        # Replaying the original acknowledged version is idempotent once no failed jobs remain.
        duplicate = await asyncio.gather(
            *[
                call(
                    session,
                    "retry_material_cleanup",
                    task_id=tid,
                    expected_version=found["version"],
                )
                for session in (e, f)
            ]
        )
        assert all(r["version"] == row["version"] and r.get("ok", True) for r in duplicate)
        (control / "pause-cleanup").unlink()
        done = await wait_state(e, tid, lambda r: r["cleanup_state"] == "done")
        completed = await asyncio.gather(
            *[
                call(
                    session,
                    "retry_material_cleanup",
                    task_id=tid,
                    expected_version=found["version"],
                )
                for session in (e, f)
            ]
        )
        assert all(r["version"] == done["version"] for r in completed)
        assert "MATERIAL_CLEANUP_FAILED" not in done["attention"]
        assert bool(done["locally_cancelled"]) == (action == "cancel_task")
        if action == "abandon_task":
            assert done["auto_mode"] == "abandoned"
        assert done["remote_state"] == "not_submitted"
    await asyncio.to_thread(third.wait, timeout=12)
    assert child.returncode == second.returncode == third.returncode == 0
    after = await asyncio.to_thread(persisted, config)
    final_job = next(j for j in after["cleanup_jobs"] if j["cleanup_id"] == job["cleanup_id"])
    assert final_job["state"] == "done" and final_job["remaining_budget"] == 1
    assert len(after["cleanup_jobs"]) == 3
    for old in before["cleanup_jobs"]:
        if old["state"] == "done":
            assert old in after["cleanup_jobs"]
    assert after["tasks"][0]["effective_parameters"] == before["tasks"][0]["effective_parameters"]
    assert deletions(control) == [1, 3, 1]
    assert material_counts(control) == [1, 1, 0]
    assert counts(control)["submit"] == counts(control)["download"] == 0
    for material in after["material_copies"]:
        assert not await asyncio.to_thread(Path(material["managed_path"]).exists)
    for i, source in enumerate(sources):
        assert await asyncio.to_thread(source.read_bytes) == f"synthetic-input-{i}".encode()
