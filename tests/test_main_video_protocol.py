"""Independent stdio clients, real backend lifecycle, synthetic supplier transport."""

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from test_artifacts import video
from test_tools import call, protocol, submit
from test_windows_integration import backend as backend
from test_windows_integration import until

WORKER = Path(__file__).with_name("main_video_backend.py")


def counts(control):
    path = control / "requests.jsonl"
    rows = (
        [json.loads(line)["kind"] for line in path.read_text().splitlines()]
        if path.exists()
        else []
    )
    return {kind: rows.count(kind) for kind in ("submit", "query", "download")}


async def wait_state(session, tid, predicate):
    async with asyncio.timeout(12):
        while True:
            row = await call(session, "get_task", task_id=tid)
            if predicate(row):
                return row
            await call(
                session, "wait_task", task_id=tid, after_version=row["version"], timeout_seconds=0.2
            )


async def delivered(session, tid, target, *, workspace=None):
    row = await wait_state(session, tid, lambda r: r["delivery"] == "partial")
    assert row["remote_state"] == "succeeded" and row["artifact_set_status"] == "unverified"
    assert "ARTIFACT_SET_UNVERIFIED" in row["attention"]
    assert row["charge"]["state"] == "not_returned"
    assert not row["generation_slot_held"] and row["cleanup_state"] != "pending"
    items = await call(session, "list_artifacts", task_id=tid)
    assert len(items["items"]) == 1
    item = items["items"][0]
    assert item["state"] == "ready"
    verified = await call(session, "verify_artifact", artifact_id=item["artifact_id"])
    expected = hashlib.sha256(video()).hexdigest()
    assert verified["sha256"] == item["sha256"] == expected
    copied = await call(
        session,
        "copy_artifact",
        artifact_id=item["artifact_id"],
        target_path=str(target),
        workspace_root=str(workspace) if workspace else None,
    )
    assert copied["copied"]
    assert (
        hashlib.sha256(await asyncio.to_thread(Path(copied["path"]).read_bytes)).hexdigest()
        == expected
    )
    assert (
        hashlib.sha256(await asyncio.to_thread(Path(item["target_path"]).read_bytes)).hexdigest()
        == expected
    )
    assert "synthetic-private" not in json.dumps([row, items, verified, copied])
    assert "base64" not in json.dumps([row, items, verified, copied]).lower()
    return item, copied


async def test_cross_frontend_delivery_then_clean_backend_restart(backend, tmp_path):
    start, control, _, _ = backend
    child = await start(worker=WORKER)
    async with protocol() as b:
        async with protocol() as a:
            accepted = await submit(a, "main-shared")
            tid = accepted["task_id"]
            await wait_state(a, tid, lambda r: r["remote_state"] == "running")
            assert (await submit(b, "main-shared"))["task_id"] == tid
            assert (await call(b, "get_service_status"))["host_count"] == 2
        assert child.poll() is None
        (control / "complete").touch()
        item, copied = await delivered(b, tid, "nested/main.mp4", workspace=tmp_path / "work")
        conflict = await call(
            b, "copy_artifact", artifact_id=item["artifact_id"], target_path=copied["path"]
        )
        assert conflict["ok"] is False
        assert (
            hashlib.sha256(await asyncio.to_thread(Path(copied["path"]).read_bytes)).hexdigest()
            == item["sha256"]
        )
        overwritten = await call(
            b,
            "copy_artifact",
            artifact_id=item["artifact_id"],
            target_path=copied["path"],
            overwrite=True,
        )
        assert overwritten["copied"]
        listed = await call(b, "list_tasks", attention_reason="ARTIFACT_SET_UNVERIFIED")
        assert tid in {r["task_id"] for r in listed["items"]}
    await asyncio.to_thread(child.wait, timeout=12)
    assert child.returncode == 0
    before = counts(control)
    assert before["submit"] == before["download"] == 1
    restarted = await start(worker=WORKER)
    async with protocol() as c:
        found = await call(c, "find_task_by_request_key", request_key="main-shared")
        assert found["task_id"] == tid
        recovered, _ = await delivered(c, tid, tmp_path / "after-restart.mp4")
        assert recovered["artifact_id"] == item["artifact_id"]
        assert recovered["target_path"] == item["target_path"]
        assert (await submit(c, "main-shared"))["task_id"] == tid
        assert counts(control) == before  # Local delivery does not query or download again.
    await asyncio.to_thread(restarted.wait, timeout=12)
    assert restarted.returncode == 0


@pytest.mark.parametrize("phase", ["download_before_publish", "download_after_publish"])
async def test_main_video_publish_crash_recovered_by_new_frontend(backend, tmp_path, phase):
    start, control, _, _ = backend
    (control / "complete").touch()
    child = await start(phase, worker=WORKER)
    async with protocol() as a:
        accepted = await submit(a, "main-crash")
        await until(lambda: child.poll() is not None)
        assert child.returncode == 91
    restarted = await start(phase, worker=WORKER)
    async with protocol() as b:
        found = await call(b, "find_task_by_request_key", request_key="main-crash")
        assert found["task_id"] == accepted["task_id"]
        await delivered(b, found["task_id"], tmp_path / "recovered.mp4")
        assert counts(control)["submit"] == 1
        assert counts(control)["download"] == (
            2 if phase == "download_before_publish" else 1
        )  # Unpublished work restarts; published proof avoids redownload.
    await asyncio.to_thread(restarted.wait, timeout=12)
    assert restarted.returncode == 0


async def test_download_attention_survives_restart_until_explicit_tool_retry(backend, tmp_path):
    start, control, _, _ = backend
    (control / "complete").touch()
    (control / "expired").touch()
    child = await start(worker=WORKER)
    async with protocol() as a:
        tid = (await submit(a, "main-expired"))["task_id"]
        await wait_state(a, tid, lambda r: "ARTIFACT_LINK_REFRESH_UNVERIFIED" in r["attention"])
    await asyncio.to_thread(child.wait, timeout=12)
    assert child.returncode == 0
    (control / "expired").unlink()  # Synthetic same URL becomes available, no refresh claim.
    restarted = await start(worker=WORKER)
    async with protocol() as b:
        row = await call(b, "get_task", task_id=tid)
        assert row["auto_mode"] == "needs_attention"
        assert row["remote_state"] == "succeeded"
        assert counts(control)["download"] == 1
        retried = await call(b, "retry_task_download", task_id=tid, expected_version=row["version"])
        assert retried.get("ok", True)
        await delivered(b, tid, tmp_path / "retry.mp4")
        row = await call(b, "get_task", task_id=tid)
        assert "ARTIFACT_LINK_REFRESH_UNVERIFIED" not in row["attention"]
        assert counts(control)["submit"] == 1 and counts(control)["download"] == 2
    await asyncio.to_thread(restarted.wait, timeout=12)
    assert restarted.returncode == 0


async def test_tracking_continues_after_last_frontend_and_backend_exit(backend, tmp_path):
    start, control, _, _ = backend
    child = await start(worker=WORKER)
    async with protocol() as a:
        tid = (await submit(a, "main-tracking"))["task_id"]
        before = await wait_state(a, tid, lambda r: r["remote_state"] == "running")
    await asyncio.to_thread(child.wait, timeout=12)
    assert child.returncode == 0
    (control / "complete").touch()
    restarted = await start(worker=WORKER)
    async with protocol() as b:
        found = await call(b, "find_task_by_request_key", request_key="main-tracking")
        assert found["task_id"] == tid
        await delivered(b, tid, tmp_path / "continued.mp4")
        after = await call(b, "get_task", task_id=tid)
        assert after["remote_id"] == before["remote_id"]
        assert counts(control)["submit"] == 1 and counts(control)["download"] == 1
    await asyncio.to_thread(restarted.wait, timeout=12)
    assert restarted.returncode == 0
