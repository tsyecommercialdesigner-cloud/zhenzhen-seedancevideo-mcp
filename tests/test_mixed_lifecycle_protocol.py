"""Mixed upload expiry and in-flight task management over isolated real MCP processes."""

import asyncio
from pathlib import Path

import pytest
from test_main_video_protocol import WORKER, delivered, wait_state
from test_material_protocol import counts, persisted
from test_multi_material_protocol import material_counts
from test_tools import call, protocol
from test_windows_integration import backend as backend
from test_windows_integration import until


async def submit_mixed(session, tmp_path):
    content = []
    sources = []
    for i, (kind, suffix) in enumerate((("image", ".png"), ("video", ".mp4"), ("audio", ".mp3"))):
        source = tmp_path / f"private-{i}{suffix}"
        await asyncio.to_thread(source.write_bytes, f"synthetic-input-{i}".encode())
        sources.append(source)
        content.append({"type": kind + "_url", kind + "_url": {"url": {"local_path": str(source)}}})
    accepted = await call(
        session,
        "submit_video",
        request_key="mixed-lifecycle",
        request={
            "model": "seedance-2.0-mini-multi",
            "prompt": "synthetic mixed references",
            "metadata": {"content": content},
        },
    )
    return accepted["task_id"], sources


@pytest.mark.parametrize("expired_index", [1, 2], ids=["video", "audio"])
async def test_mixed_expiry_reuploads_only_expired_reference(backend, tmp_path, expired_index):
    start, control, _, config = backend
    phase = f"material-multi-expiry-{expired_index}-mixed-video"
    (control / "release-upload").touch()
    child = await start(phase, worker=WORKER)
    async with protocol() as a:
        tid, sources = await submit_mixed(a, tmp_path)
        await until(lambda: child.poll() is not None)
        assert child.returncode == 91
    before = await asyncio.to_thread(persisted, config)
    assert material_counts(control) == [1, 1, 1] and counts(control)["submit"] == 0
    await asyncio.sleep(1.1)  # Explicit synthetic TTL, not a supplier lifetime assumption.
    for source in sources:
        await asyncio.to_thread(source.unlink)
    (control / "complete").touch()
    restarted = await start(phase, worker=WORKER)
    async with protocol() as b:
        assert (await call(b, "find_task_by_request_key", request_key="mixed-lifecycle"))[
            "task_id"
        ] == tid
        await delivered(b, tid, "mixed/video.mp4", workspace=tmp_path / "workspace")
    await asyncio.to_thread(restarted.wait, timeout=12)
    assert restarted.returncode == 0
    after = await asyncio.to_thread(persisted, config)
    assert material_counts(control) == [1 + (i == expired_index) for i in range(3)]
    assert counts(control)["submit"] == counts(control)["download"] == 1
    assert after["material_copies"] == before["material_copies"]
    assert after["tasks"][0]["effective_parameters"] == before["tasks"][0]["effective_parameters"]
    materials = sorted(after["material_copies"], key=lambda r: r["ordinal"])
    for i, material in enumerate(materials):
        old = next(r for r in before["uploads"] if r["material_id"] == material["material_id"])
        new = next(r for r in after["uploads"] if r["material_id"] == material["material_id"])
        if i == expired_index:
            assert new["remaining_budget"] == old["remaining_budget"] - 1
            assert new["url"] != old["url"]
        else:
            assert new == old
        assert (
            await asyncio.to_thread(Path(material["managed_path"]).read_bytes)
            == f"synthetic-input-{i}".encode()
        )
    assert not after["cleanup_jobs"]


@pytest.mark.parametrize("action", ["cancel_task", "abandon_task"])
async def test_mixed_inflight_management_cleans_all_copies_and_survives_restart(
    backend, tmp_path, action
):
    start, control, _, config = backend
    phase = "material-multi-cleanup-mixed-video"
    (control / "release-upload").touch()
    child = await start(phase, worker=WORKER)
    async with protocol() as a, protocol() as b:
        tid, sources = await submit_mixed(a, tmp_path)
        await until(lambda: (control / "second-inflight").exists())
        row = await call(b, "get_task", task_id=tid)
        args = {"task_id": tid, "expected_version": row["version"]}
        if action == "abandon_task":
            args.update(reason="synthetic cleanup", acknowledge_remote_may_continue=True)
        result = await call(b, action, **args)
        assert result.get("ok", True)
        if action == "cancel_task":
            assert result["locally_cancelled"]
        await wait_state(b, tid, lambda r: r["cleanup_state"] == "done")
        assert material_counts(control) == [1, 1, 0]
        assert counts(control)["submit"] == counts(control)["download"] == 0
    await asyncio.to_thread(child.wait, timeout=12)
    before = await asyncio.to_thread(persisted, config)
    assert len(before["material_copies"]) == 3
    for material in before["material_copies"]:
        assert not await asyncio.to_thread(Path(material["managed_path"]).exists)
    (control / "release-second").touch()
    restarted = await start(phase, worker=WORKER)
    async with protocol() as c:
        found = await call(c, "find_task_by_request_key", request_key="mixed-lifecycle")
        assert found["task_id"] == tid and found["cleanup_state"] == "done"
        if action == "cancel_task":
            assert found["locally_cancelled"]
        else:
            assert found["auto_mode"] == "abandoned" and not found["locally_cancelled"]
        await call(c, "wait_task", task_id=tid, after_version=found["version"], timeout_seconds=0.3)
        assert material_counts(control) == [1, 1, 0] and counts(control)["submit"] == 0
    await asyncio.to_thread(restarted.wait, timeout=12)
    assert child.returncode == restarted.returncode == 0
    after = await asyncio.to_thread(persisted, config)
    for old, new in zip(before["uploads"], after["uploads"], strict=True):
        assert new == (old | {"state": "pending"} if old["state"] == "uploading" else old)
    assert any(
        r["state"] == "reconciled" for r in after["attempts"] if r["phase"].startswith("upload:")
    )
    assert after["cleanup_jobs"] == before["cleanup_jobs"]
    for i, source in enumerate(sources):
        assert await asyncio.to_thread(source.read_bytes) == f"synthetic-input-{i}".encode()
