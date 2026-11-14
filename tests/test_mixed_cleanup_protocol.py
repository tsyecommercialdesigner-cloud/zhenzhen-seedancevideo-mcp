"""Durable mixed-input cleanup failures and explicit recovery over real stdio clients."""

import asyncio
import json
from pathlib import Path

import pytest
from test_main_video_protocol import WORKER, wait_state
from test_material_protocol import counts, persisted
from test_mixed_lifecycle_protocol import submit_mixed
from test_multi_material_protocol import material_counts
from test_tools import call, protocol
from test_windows_integration import backend as backend
from test_windows_integration import until


def deletions(control):
    kinds = [
        json.loads(line)["kind"] for line in (control / "requests.jsonl").read_text().splitlines()
    ]
    return [kinds.count(f"delete-{i}") for i in range(3)]


@pytest.mark.parametrize("action", ["cancel_task", "abandon_task"])
@pytest.mark.parametrize("exhaust", [False, True])
async def test_mixed_cleanup_budget_and_explicit_recovery(
    backend, tmp_path, monkeypatch, action, exhaust
):
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_CLEANUP_RETRIES", "1")
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_CLEANUP_CONCURRENCY", "1")
    start, control, _, config = backend
    phase = "material-multi-cleanup-" + ("exhaust" if exhaust else "retry") + "-mixed-video"
    (control / "release-upload").touch()
    child = await start(phase, worker=WORKER)
    async with protocol() as a, protocol() as b:
        tid, sources = await submit_mixed(a, tmp_path)
        await until(lambda: (control / "second-inflight").exists())
        row = await call(b, "get_task", task_id=tid)
        args = {"task_id": tid, "expected_version": row["version"]}
        if action == "abandon_task":
            args.update(reason="synthetic cleanup failure", acknowledge_remote_may_continue=True)
        assert (await call(b, action, **args)).get("ok", True)
        if exhaust:
            await wait_state(b, tid, lambda r: r["cleanup_state"] == "failed")
        else:
            await until(lambda: child.poll() is not None)
            assert child.returncode == 91
    await asyncio.to_thread(child.wait, timeout=12)
    before = await asyncio.to_thread(persisted, config)
    materials = sorted(before["material_copies"], key=lambda m: m["ordinal"])
    failed_id = materials[1]["material_id"]
    old = next(j for j in before["cleanup_jobs"] if j["material_id"] == failed_id)
    assert old["remaining_budget"] == (0 if exhaust else 1)
    assert old["state"] == ("failed" if exhaust else "pending")
    assert await asyncio.to_thread(Path(materials[1]["managed_path"]).exists)
    assert not await asyncio.to_thread(Path(materials[0]["managed_path"]).exists)
    prior_counts = deletions(control)
    assert prior_counts[0] == 1 and prior_counts[1] == (2 if exhaust else 1)
    (control / "release-cleanup").touch()
    (control / "release-second").touch()
    restarted = await start(phase, worker=WORKER)
    async with protocol() as c, protocol() as d:
        found = await call(c, "find_task_by_request_key", request_key="mixed-lifecycle")
        assert found["task_id"] == tid
        if exhaust:
            assert found["cleanup_state"] == "failed"
            assert "MATERIAL_CLEANUP_FAILED" in found["attention"]
            await call(
                c, "wait_task", task_id=tid, after_version=found["version"], timeout_seconds=0.3
            )
            assert deletions(control) == prior_counts
            stale = await call(
                d, "retry_material_cleanup", task_id=tid, expected_version=found["version"] - 1
            )
            assert stale["ok"] is False
            assert deletions(control) == prior_counts
            retry = await call(
                d, "retry_material_cleanup", task_id=tid, expected_version=found["version"]
            )
            assert retry.get("ok", True)
        final = await wait_state(c, tid, lambda r: r["cleanup_state"] == "done")
        assert "MATERIAL_CLEANUP_FAILED" not in final["attention"]
        assert final["remote_state"] == "not_submitted"
        assert bool(final["locally_cancelled"]) == (action == "cancel_task")
        if action == "abandon_task":
            assert final["auto_mode"] == "abandoned"
        assert (
            await call(d, "retry_material_cleanup", task_id=tid, expected_version=final["version"])
        ).get("ok", True)
        assert deletions(control) == [1, 3 if exhaust else 2, 1]
        assert material_counts(control) == [1, 1, 0]
        assert counts(control)["submit"] == counts(control)["download"] == 0
    await asyncio.to_thread(restarted.wait, timeout=12)
    assert restarted.returncode == 0
    after = await asyncio.to_thread(persisted, config)
    new = next(j for j in after["cleanup_jobs"] if j["material_id"] == failed_id)
    assert new["cleanup_id"] == old["cleanup_id"] and new["state"] == "done"
    assert new["remaining_budget"] == (1 if exhaust else 0)
    for old_job in before["cleanup_jobs"]:
        if old_job["state"] == "done":
            assert old_job in after["cleanup_jobs"]
    assert after["tasks"][0]["effective_parameters"] == before["tasks"][0]["effective_parameters"]
    for i, material in enumerate(materials):
        assert not await asyncio.to_thread(Path(material["managed_path"]).exists)
        assert await asyncio.to_thread(sources[i].read_bytes) == f"synthetic-input-{i}".encode()
