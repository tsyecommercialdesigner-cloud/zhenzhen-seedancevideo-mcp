"""MCP recovery of mixed cleanup deletion/commit crash windows; synthetic HTTP only."""

import asyncio
import json
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


@pytest.mark.parametrize("point", ["before", "after"])
@pytest.mark.parametrize("retries,action", [(0, "cancel_task"), (1, "abandon_task")])
async def test_mixed_cleanup_delete_commit_crash(
    backend, tmp_path, monkeypatch, point, retries, action
):
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_CLEANUP_RETRIES", "1")
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_CLEANUP_CONCURRENCY", "1")
    start, control, _, config = backend
    phase = (
        f"material-multi-cleanup-crash-{point}-" + ("zero-" if retries == 0 else "") + "mixed-video"
    )
    (control / "release-upload").touch()
    child = await start(phase, worker=WORKER)
    async with protocol() as a, protocol() as b:
        tid, sources = await submit_mixed(a, tmp_path)
        await until(lambda: (control / "second-inflight").exists())
        row = await call(b, "get_task", task_id=tid)
        args = {"task_id": tid, "expected_version": row["version"]}
        if action == "abandon_task":
            args.update(reason="synthetic deletion crash", acknowledge_remote_may_continue=True)
        # Cleanup runs independently; the task management transaction is acknowledged first.
        result = await call(b, action, **args)
        assert result.get("ok", True)
        await until(lambda: child.poll() is not None)
        assert child.returncode == 91
    before = await asyncio.to_thread(persisted, config)
    materials = sorted(before["material_copies"], key=lambda m: m["ordinal"])
    middle = materials[1]
    old = next(j for j in before["cleanup_jobs"] if j["material_id"] == middle["material_id"])
    assert old["state"] == "deleting" and old["remaining_budget"] == retries
    assert await asyncio.to_thread(Path(middle["managed_path"]).exists) == (point == "before")
    assert not await asyncio.to_thread(Path(materials[0]["managed_path"]).exists)
    assert await asyncio.to_thread(Path(materials[2]["managed_path"]).exists) == (retries == 1)
    assert deletions(control) == [1, 2 if retries == 0 else 1, 1 if retries == 0 else 0]
    (control / "release-second").touch()
    restarted = await start(phase, worker=WORKER)
    async with protocol() as c, protocol() as d:
        assert (await call(c, "find_task_by_request_key", request_key="mixed-lifecycle"))[
            "task_id"
        ] == tid
        if point == "before" and retries == 0:
            failed = await wait_state(c, tid, lambda r: r["cleanup_state"] == "failed")
            assert "MATERIAL_CLEANUP_FAILED" in failed["attention"]
            assert await asyncio.to_thread(Path(middle["managed_path"]).exists)
            assert deletions(control)[1] == 2  # No new delete allowed without a new budget.
            assert (
                await call(
                    d, "retry_material_cleanup", task_id=tid, expected_version=failed["version"]
                )
            ).get("ok", True)
        final = await wait_state(c, tid, lambda r: r["cleanup_state"] == "done")
        assert "MATERIAL_CLEANUP_FAILED" not in final["attention"]
        assert final["remote_state"] == "not_submitted"
        assert bool(final["locally_cancelled"]) == (action == "cancel_task")
        if action == "abandon_task":
            assert final["auto_mode"] == "abandoned"
        prior = deletions(control)
        assert (
            await call(d, "retry_material_cleanup", task_id=tid, expected_version=final["version"])
        ).get("ok", True)
        assert deletions(control) == prior
    await asyncio.to_thread(restarted.wait, timeout=12)
    assert restarted.returncode == 0
    after = await asyncio.to_thread(persisted, config)
    new = next(j for j in after["cleanup_jobs"] if j["material_id"] == middle["material_id"])
    assert new["cleanup_id"] == old["cleanup_id"] and new["state"] == "done"
    assert new["remaining_budget"] == (1 if point == "before" and retries == 0 else 0)
    for job in before["cleanup_jobs"]:
        if job["state"] == "done":
            assert job in after["cleanup_jobs"]
    assert after["tasks"][0]["effective_parameters"] == before["tasks"][0]["effective_parameters"]
    assert material_counts(control) == [1, 1, 0]
    assert counts(control)["submit"] == counts(control)["download"] == 0
    kinds = [
        json.loads(line)["kind"] for line in (control / "requests.jsonl").read_text().splitlines()
    ]
    assert [kinds.count(f"removed-{i}") for i in range(3)] == [1, 1, 1]
    assert deletions(control) == [1, 3 if point == "before" and retries == 0 else 2, 1]
    for i, material in enumerate(materials):
        assert not await asyncio.to_thread(Path(material["managed_path"]).exists)
        assert await asyncio.to_thread(sources[i].read_bytes) == f"synthetic-input-{i}".encode()
