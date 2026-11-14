"""Partial multi-input uploads and concurrent MCP admission across backend restarts."""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from test_main_video_protocol import WORKER, delivered, wait_state
from test_material_protocol import counts, persisted
from test_tools import call, protocol
from test_windows_integration import backend as backend
from test_windows_integration import until

from zhenzhen_seedance_video.runtime import _connect, read_record


@asynccontextmanager
async def pinned_start(start, phase, config, network_guard):
    """Hold a real authenticated lease while the two stdio processes initialize."""
    child = await start(phase, worker=WORKER)
    directory = config.root / "runtime"
    record = await asyncio.to_thread(read_record, directory / "discovery.json")
    assert record["launch_id"] is None and child.poll() is None
    port = record["port"]
    network_guard.add(port)
    client = None
    try:
        client = await _connect(directory, record, {})
        yield child, client, record
    finally:
        if client is not None:
            await client.close()
        network_guard.discard(port)


def material_counts(control):
    rows = [
        json.loads(line)["kind"] for line in (control / "requests.jsonl").read_text().splitlines()
    ]
    return [rows.count(f"material-{i}") for i in range(3)]


@pytest.mark.parametrize("layout", ["images", "mixed-video", "mixed-audio"])
@pytest.mark.parametrize("exhaust", [False, True])
async def test_partial_upload_concurrent_dedup_restart(
    backend, tmp_path, monkeypatch, exhaust, layout, network_guard
):
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_UPLOAD_RETRIES", "1")
    # Allow both real stdio subprocesses to attach before the synthetic backend drains.
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_SHUTDOWN_GRACE_SECONDS", "5")
    start, control, _, config = backend
    kinds = {
        "images": [("image", ".png")] * 3,
        "mixed-video": [("image", ".png"), ("video", ".mp4"), ("audio", ".mp3")],
        "mixed-audio": [("video", ".mp4"), ("audio", ".mp3"), ("image", ".png")],
    }[layout]
    sources = [tmp_path / f"private-{i}{suffix}" for i, (_, suffix) in enumerate(kinds)]
    for i, source in enumerate(sources):
        await asyncio.to_thread(source.write_bytes, f"synthetic-input-{i}".encode())
    request = {
        "model": "seedance-2.0-mini-multi",
        "prompt": "three synthetic references",
        "metadata": {
            "content": [
                {"type": kind + "_url", kind + "_url": {"url": {"local_path": str(p)}}}
                for p, (kind, _) in zip(sources, kinds, strict=True)
            ]
        },
    }

    async def submit(session, payload=request):
        return await call(session, "submit_video", request_key="multi-shared", request=payload)

    phase = "material-multi-exhaust" if exhaust else "material-multi-failure"
    if layout != "images":
        phase += "-" + layout
    async with (
        pinned_start(start, phase, config, network_guard) as (child, startup_lease, record),
        protocol() as a,
        protocol() as b,
    ):
        assert (await call(a, "get_service_status"))["pid"] == record["pid"]
        await startup_lease.close()
        first, second = await asyncio.gather(submit(a), submit(b))
        tid = first["task_id"]
        assert second["task_id"] == tid
        conflict = await submit(b, request | {"prompt": "different intention"})
        assert conflict["ok"] is False
        (control / "release-upload").touch()
        if exhaust:
            await wait_state(a, tid, lambda r: "UPLOAD_RETRIES_EXHAUSTED" in r["attention"])
        else:
            await until(lambda: child.poll() is not None)
            assert child.returncode == 91
    await asyncio.to_thread(child.wait, timeout=12)
    before = await asyncio.to_thread(persisted, config)
    assert len(before["tasks"]) == 1 and len(before["material_copies"]) == 3
    assert len(before["uploads"]) == 2
    assert material_counts(control) == [1, 2 if exhaust else 1, 0]
    assert counts(control)["submit"] == 0
    first_id = before["material_copies"][0]["material_id"]
    cached = next(r for r in before["uploads"] if r["material_id"] == first_id)
    assert cached["state"] == "ready" and cached["remaining_budget"] == 1
    (control / "complete").touch()
    async with (
        pinned_start(start, phase, config, network_guard) as (restarted, startup_lease, record),
        protocol() as c,
        protocol() as d,
    ):
        assert (await call(c, "get_service_status"))["pid"] == record["pid"]
        await startup_lease.close()
        left, right = await asyncio.gather(submit(c), submit(d))
        assert left["task_id"] == right["task_id"] == tid
        if exhaust:
            row = await call(d, "get_task", task_id=tid)
            assert row["auto_mode"] == "needs_attention"
            await call(
                d, "wait_task", task_id=tid, after_version=row["version"], timeout_seconds=0.3
            )
        else:
            await delivered(d, tid, tmp_path / "multi.mp4")
        assert material_counts(control) == [1, 2, 0 if exhaust else 1]
        assert counts(control)["submit"] == (0 if exhaust else 1)
        assert counts(control)["download"] == (0 if exhaust else 1)
    await asyncio.to_thread(restarted.wait, timeout=12)
    assert restarted.returncode == 0
    after = await asyncio.to_thread(persisted, config)
    assert len(after["tasks"]) == 1 and len(after["material_copies"]) == 3
    assert {r["material_id"] for r in after["material_copies"]} == {
        r["material_id"] for r in before["material_copies"]
    }
    assert next(r for r in after["uploads"] if r["material_id"] == first_id) == cached
    assert after["tasks"][0]["effective_parameters"] == before["tasks"][0]["effective_parameters"]
    materials = sorted(after["material_copies"], key=lambda r: r["ordinal"])
    budgets = {r["material_id"]: r["remaining_budget"] for r in after["uploads"]}
    assert budgets[materials[1]["material_id"]] == 0
    if not exhaust:
        assert budgets[materials[2]["material_id"]] == 1
    assert len({r["sha256"] for r in materials}) == 3
    for material in materials:
        assert await asyncio.to_thread(Path(material["managed_path"]).exists)
    assert not after["cleanup_jobs"]
    for i, source in enumerate(sources):
        assert await asyncio.to_thread(source.read_bytes) == f"synthetic-input-{i}".encode()
