"""Cleanup transaction rollback and storage-fault gating through independent MCP clients."""

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


@pytest.mark.parametrize("recovery_fault", ["none", "worker", "startup_scan"])
@pytest.mark.parametrize("point", ["intent", "complete"])
async def test_cleanup_storage_failure_gates_effects_and_recovers(
    backend, tmp_path, monkeypatch, point, recovery_fault
):
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_CLEANUP_CONCURRENCY", "1")
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_CLEANUP_RETRIES", "1")
    start, control, _, config = backend
    phase = f"material-multi-cleanup-storage-{point}-mixed-video"
    (control / "release-upload").touch()
    (control / "release-cleanup").touch()
    child = await start(phase, worker=WORKER)
    async with protocol() as a, protocol() as b:
        tid, sources = await submit_mixed(a, tmp_path)
        await until(lambda: (control / "second-inflight").exists())
        row = await call(b, "get_task", task_id=tid)
        result = await call(
            b,
            "abandon_task",
            task_id=tid,
            expected_version=row["version"],
            reason="synthetic storage failure",
            acknowledge_remote_may_continue=True,
        )
        assert result.get("ok", True)
        await until(lambda: (control / "storage-injected").exists())
        status = await call(a, "get_service_status")
        assert status["storage_fault"] and status["stale"]
        snapshot = await call(b, "get_task", task_id=tid)
        assert snapshot["cleanup_state"] != "done" and snapshot["auto_mode"] == "abandoned"
        rejected = await call(
            a, "retry_material_cleanup", task_id=tid, expected_version=snapshot["version"]
        )
        assert rejected["ok"] is False and rejected["error"] == "STORAGE_FAULT"
        rejected = await call(
            b,
            "submit_video",
            request_key="during-cleanup-fault",
            request={"model": "seedance-2.0-mini-t2v", "prompt": "synthetic blocked"},
        )
        assert rejected["ok"] is False and rejected["error"] == "STORAGE_FAULT"
        await call(
            a, "wait_task", task_id=tid, after_version=snapshot["version"], timeout_seconds=0.3
        )

        async def observe(session):
            health, task, listing, found, waiting = await asyncio.gather(
                call(session, "get_service_status"),
                call(session, "get_task", task_id=tid),
                call(session, "list_tasks"),
                call(session, "find_task_by_request_key", request_key="mixed-lifecycle"),
                call(
                    session,
                    "wait_task",
                    task_id=tid,
                    after_version=snapshot["version"],
                    timeout_seconds=0.2,
                ),
            )
            assert health["storage_fault"] and health["stale"]
            assert task["stale"] and listing["stale"]
            assert task["version"] == found["version"] == snapshot["version"]
            assert listing["items"][0]["task_id"] == found["task_id"] == tid
            assert waiting["version"] == task["version"]
            return task

        left, right = await asyncio.gather(observe(a), observe(b))
        assert left == right
        versioned = {"task_id": tid, "expected_version": snapshot["version"]}
        operations = [
            ("cancel_task", versioned),
            (
                "abandon_task",
                versioned | {"reason": "blocked", "acknowledge_remote_may_continue": True},
            ),
            ("resume_task_tracking", versioned),
            ("retry_unsubmitted_task", versioned),
            ("retry_task_download", versioned),
            ("retry_material_cleanup", versioned),
            ("refresh_task", {"task_id": tid}),
        ]
        denied = await asyncio.gather(
            *[call(session, name, **args) for session in (a, b) for name, args in operations]
        )
        assert all(r.get("ok") is False and r.get("error") == "STORAGE_FAULT" for r in denied), [
            (operations[i % len(operations)][0], r.get("error")) for i, r in enumerate(denied)
        ]
        assert (await call(a, "get_task", task_id=tid))["version"] == snapshot["version"]
        assert child.poll() is None
        assert deletions(control) == [1, int(point == "complete"), 0]
        assert counts(control)["submit"] == counts(control)["download"] == 0
    await asyncio.to_thread(child.wait, timeout=12)
    assert child.returncode == 0
    before = await asyncio.to_thread(persisted, config)
    assert len(before["tasks"]) == 1
    materials = sorted(before["material_copies"], key=lambda m: m["ordinal"])
    old = next(j for j in before["cleanup_jobs"] if j["material_id"] == materials[1]["material_id"])
    assert old["state"] == ("new" if point == "intent" else "deleting")
    assert await asyncio.to_thread(Path(materials[1]["managed_path"]).exists) == (point == "intent")
    assert await asyncio.to_thread(Path(materials[2]["managed_path"]).exists)
    (control / "release-second").touch()
    if recovery_fault == "worker":
        # Re-arm only the synthetic one-shot fault, never the persisted cleanup budget.
        (control / "storage-injected").unlink()
        faulted_restart = await start(phase, worker=WORKER)
        async with protocol() as recovering_host, protocol() as joining_host:
            await until(lambda: (control / "storage-injected").exists())
            observations = await asyncio.gather(
                call(recovering_host, "get_service_status"),
                call(joining_host, "get_service_status"),
            )
            assert all(r["storage_fault"] and r["stale"] for r in observations)
            assert all(r["host_count"] == 2 for r in observations)
            record = json.loads((config.root / "runtime/discovery.json").read_text())
            assert observations[0]["pid"] == observations[1]["pid"] == record["pid"]
            rows = await asyncio.gather(
                call(recovering_host, "get_task", task_id=tid),
                call(joining_host, "find_task_by_request_key", request_key="mixed-lifecycle"),
            )
            assert rows[0]["version"] == rows[1]["version"]
            assert all(r["cleanup_state"] != "done" and r["stale"] for r in rows)
            denied = await asyncio.gather(
                *[
                    call(
                        session,
                        "retry_material_cleanup",
                        task_id=tid,
                        expected_version=rows[0]["version"],
                    )
                    for session in (recovering_host, joining_host)
                ]
            )
            assert all(r["error"] == "STORAGE_FAULT" for r in denied)
            assert faulted_restart.poll() is None
        await asyncio.to_thread(faulted_restart.wait, timeout=12)
        assert faulted_restart.returncode == 0
        interrupted = await asyncio.to_thread(persisted, config)
        retry_job = next(
            j for j in interrupted["cleanup_jobs"] if j["cleanup_id"] == old["cleanup_id"]
        )
        assert retry_job["state"] == old["state"]
        assert retry_job["remaining_budget"] == (
            old["remaining_budget"] if point == "intent" else 0
        )
        completed_before = [j for j in before["cleanup_jobs"] if j["state"] == "done"]
        assert all(j in interrupted["cleanup_jobs"] for j in completed_before)
        assert len(interrupted["tasks"]) == 1
        assert deletions(control) == [1, 2 if point == "complete" else 0, 0]
        assert material_counts(control) == [1, 1, 0]
        assert counts(control)["submit"] == counts(control)["download"] == 0
    if recovery_fault == "startup_scan":
        discovery = config.root / "runtime/discovery.json"
        old_discovery = discovery.read_bytes()
        side_effects = (deletions(control), material_counts(control), counts(control))
        (control / "fail-startup-scan").touch()
        failed_start = await start(phase, worker=WORKER, expect_startup_failure=True)
        assert failed_start.returncode != 0
        assert (control / "startup-scan-injected").exists()
        assert not (control / "startup-rpc-started").exists()
        assert discovery.read_bytes() == old_discovery
        interrupted = await asyncio.to_thread(persisted, config)
        for table in ("cleanup_jobs", "material_copies"):
            assert interrupted[table] == before[table]
        expected_uploads = [
            row | {"state": "pending"} if row["state"] == "uploading" else row
            for row in before["uploads"]
        ]
        assert interrupted["uploads"] == expected_uploads
        assert len(interrupted["tasks"]) == 1
        assert interrupted["tasks"][0]["auto_mode"] == "abandoned"
        assert (deletions(control), material_counts(control), counts(control)) == side_effects
        assert await asyncio.to_thread(Path(materials[1]["managed_path"]).exists) == (
            point == "intent"
        )
        assert await asyncio.to_thread(Path(materials[2]["managed_path"]).exists)
    restarted = await start(phase, worker=WORKER)
    if recovery_fault == "startup_scan":
        assert (control / "startup-rpc-started").exists()
    async with protocol() as c, protocol() as d:
        assert (await call(c, "find_task_by_request_key", request_key="mixed-lifecycle"))[
            "task_id"
        ] == tid
        final = await wait_state(d, tid, lambda r: r["cleanup_state"] == "done")
        assert not (await call(c, "get_service_status"))["storage_fault"]
        assert final["auto_mode"] == "abandoned" and final["remote_state"] == "not_submitted"
        assert "MATERIAL_CLEANUP_FAILED" not in final["attention"]
        replies = await asyncio.gather(
            *[
                call(
                    session,
                    "retry_material_cleanup",
                    task_id=tid,
                    expected_version=snapshot["version"],
                )
                for session in (c, d)
            ]
        )
        assert all(r.get("ok", True) and r["version"] == final["version"] for r in replies)
    await asyncio.to_thread(restarted.wait, timeout=12)
    assert restarted.returncode == 0
    after = await asyncio.to_thread(persisted, config)
    assert len(after["tasks"]) == 1
    new = next(j for j in after["cleanup_jobs"] if j["cleanup_id"] == old["cleanup_id"])
    assert new["state"] == "done" and new["remaining_budget"] == (1 if point == "intent" else 0)
    assert after["tasks"][0]["effective_parameters"] == before["tasks"][0]["effective_parameters"]
    assert deletions(control) == [1, 1 if point == "intent" else 2, 1]
    assert material_counts(control) == [1, 1, 0]
    assert counts(control)["submit"] == counts(control)["download"] == 0
    for i, material in enumerate(materials):
        assert not await asyncio.to_thread(Path(material["managed_path"]).exists)
        assert await asyncio.to_thread(sources[i].read_bytes) == f"synthetic-input-{i}".encode()

    # A further normal restart cannot replenish cleanup budgets or repeat completed work.
    third = await start(phase, worker=WORKER)
    async with protocol() as e, protocol() as f:
        replies = await asyncio.gather(
            *[
                call(
                    session,
                    "retry_material_cleanup",
                    task_id=tid,
                    expected_version=snapshot["version"],
                )
                for session in (e, f)
            ]
        )
        assert all(r.get("ok", True) and r["version"] == final["version"] for r in replies)
        assert not (await call(e, "get_service_status"))["storage_fault"]
    await asyncio.to_thread(third.wait, timeout=12)
    assert third.returncode == 0
    again = await asyncio.to_thread(persisted, config)
    assert again["cleanup_jobs"] == after["cleanup_jobs"]
    assert again["material_copies"] == after["material_copies"]
    assert again["tasks"][0]["version"] == after["tasks"][0]["version"]
    assert deletions(control) == [1, 1 if point == "intent" else 2, 1]
    assert material_counts(control) == [1, 1, 0]
    assert counts(control)["submit"] == counts(control)["download"] == 0
