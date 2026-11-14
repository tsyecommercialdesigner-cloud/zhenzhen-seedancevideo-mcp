"""Local input through real MCP/runtime/upload pipeline; no supplier connections."""

import asyncio
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from test_main_video_protocol import WORKER, delivered, wait_state
from test_tools import call, protocol
from test_windows_integration import backend as backend
from test_windows_integration import until

ORIGINAL = b"synthetic-original-image"


def persisted(config):
    # Read only after the owning backend has exited, never inspect production state.
    with sqlite3.connect(config.state_dir / "tasks.sqlite3") as connection:
        connection.row_factory = sqlite3.Row
        return {
            table: [dict(r) for r in connection.execute("SELECT * FROM " + table)]
            for table in ("tasks", "material_copies", "uploads", "attempts", "cleanup_jobs")
        }


def counts(control):
    rows = [
        json.loads(line)["kind"] for line in (control / "requests.jsonl").read_text().splitlines()
    ]
    return {kind: rows.count(kind) for kind in ("upload", "submit", "query", "download")}


@pytest.mark.parametrize("phase", ["material-upload", "material-prepared", "material-tracking"])
async def test_local_material_full_protocol_restart(backend, tmp_path, phase):
    start, control, _, config = backend
    source = tmp_path / "private-original.png"
    await asyncio.to_thread(source.write_bytes, ORIGINAL)
    request = {
        "model": "seedance-2.0-mini-i2v",
        "prompt": "synthetic fox",
        "images": [{"local_path": str(source)}],
    }
    child = await start(phase, worker=WORKER)
    async with protocol() as a, protocol() as observer:
        accepted = await call(a, "submit_video", request_key="local-input", request=request)
        tid = accepted["task_id"]
        duplicate = await call(observer, "submit_video", request_key="local-input", request=request)
        assert duplicate["task_id"] == tid
        await until(lambda: (control / "upload-entered").exists())
        # Admission has acknowledged a complete owned copy; the user's original may change.
        await asyncio.to_thread(source.write_bytes, b"changed-original")
        (control / "release-upload").touch()
        if phase == "material-tracking":
            await wait_state(observer, tid, lambda r: r["remote_state"] == "running")
        else:
            await until(lambda: child.poll() is not None)
            assert child.returncode == 91
    await asyncio.to_thread(child.wait, timeout=12)
    assert child.returncode == (0 if phase == "material-tracking" else 91)
    before = await asyncio.to_thread(persisted, config)
    assert len(before["tasks"]) == len(before["material_copies"]) == len(before["uploads"]) == 1
    material = before["material_copies"][0]
    managed = Path(material["managed_path"])
    assert await asyncio.to_thread(managed.read_bytes) == ORIGINAL
    assert material["sha256"] == hashlib.sha256(ORIGINAL).hexdigest()
    original_budget = before["uploads"][0]["remaining_budget"]
    assert not before["cleanup_jobs"]
    if phase != "material-tracking":
        assert counts(control)["submit"] == 0
    (control / "complete").touch()
    restarted = await start(phase, worker=WORKER)
    async with protocol() as b:
        found = await call(b, "find_task_by_request_key", request_key="local-input")
        assert found["task_id"] == tid
        await delivered(b, tid, "video/main.mp4", workspace=tmp_path / "workspace")
        row = await call(b, "get_task", task_id=tid)
        assert row["artifact_set_status"] == "unverified" and row["delivery"] == "partial"
        assert row["charge"]["state"] == "not_returned"
        assert await asyncio.to_thread(managed.read_bytes) == ORIGINAL
        assert await asyncio.to_thread(source.read_bytes) == b"changed-original"
        assert counts(control)["submit"] == counts(control)["download"] == 1
        assert counts(control)["upload"] == (2 if phase == "material-upload" else 1)
    await asyncio.to_thread(restarted.wait, timeout=12)
    assert restarted.returncode == 0
    after = await asyncio.to_thread(persisted, config)
    assert after["tasks"][0]["effective_parameters"] == before["tasks"][0]["effective_parameters"]
    assert after["material_copies"][0]["material_id"] == material["material_id"]
    assert after["uploads"][0]["remaining_budget"] == original_budget - (phase == "material-upload")
    assert not after["cleanup_jobs"]  # Unknown full collection must retain the input copy.
    upload_attempts = [r for r in after["attempts"] if r["phase"].startswith("upload:")]
    assert len(upload_attempts) == (2 if phase == "material-upload" else 1)
    if phase == "material-upload":
        assert upload_attempts[0]["state"] == "reconciled"
