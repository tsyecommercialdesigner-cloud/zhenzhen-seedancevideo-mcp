import asyncio
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_artifacts import video
from test_tools import call, protocol, submit

from zhenzhen_seedance_video.config import load_configuration

WORKER = Path(__file__).with_name("synthetic_backend.py")


async def until(check, seconds=10):
    async with asyncio.timeout(seconds):
        while True:
            value = check()
            if value:
                return value
            await asyncio.sleep(0.03)


@pytest.fixture
async def backend(monkeypatch, tmp_path, fake_http):
    for key, value in {
        "API_KEY": "synthetic",
        "POLL_INTERVAL_SECONDS": "1",
        "SHUTDOWN_GRACE_SECONDS": "2",
        "SHUTDOWN_DRAIN_SECONDS": "1",
        "HEARTBEAT_SECONDS": "1",
        "LEASE_TIMEOUT_SECONDS": "3",
    }.items():
        monkeypatch.setenv("ZHENZHEN_SEEDANCE_" + key, value)
    config = load_configuration()
    control = tmp_path / "control"
    control.mkdir()
    children = []
    logs = []

    async def start(phase="none", *, worker=WORKER, expect_startup_failure=False):
        previous = None
        record_path = config.root / "runtime/discovery.json"
        if record_path.exists():
            previous = json.loads(record_path.read_text())["instance_id"]
        log = (control / f"child-{len(children)}.log").open("w", encoding="utf-8")
        logs.append(log)
        child = await asyncio.to_thread(
            subprocess.Popen,
            [sys.executable, str(worker), str(control), fake_http.url, phase],
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        children.append(child)

        def ready():
            if child.poll() is not None:
                raise AssertionError("Synthetic backend exited before discovery")
            if record_path.exists():
                try:
                    record = json.loads(record_path.read_text())
                except (PermissionError, FileNotFoundError):
                    # Windows publication may briefly deny a reader; until() stays bounded.
                    return None
                return record if record["instance_id"] != previous else None

        if expect_startup_failure:
            await asyncio.to_thread(child.wait, timeout=12)
            assert child.returncode != 0
        else:
            await until(ready)
        return child

    try:
        yield start, control, fake_http, config
    finally:
        for child in children:
            if child.poll() is None:
                await asyncio.to_thread(child.wait, timeout=12)
            assert child.poll() is not None
        for log in logs:
            log.close()


async def test_two_frontends_dedup_copy_conflict_and_forced_frontend_exit(
    backend, tmp_path, monkeypatch
):
    # Both stdio clients must attach to the owned synthetic backend before it drains.
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_SHUTDOWN_GRACE_SECONDS", "5")
    start, control, http, config = backend
    child = await start()
    discovery = json.loads(
        await asyncio.to_thread((config.root / "runtime/discovery.json").read_text)
    )
    assert discovery["launch_id"] is None
    async with protocol() as a, protocol() as b:
        first, second = await asyncio.gather(submit(a, "same"), submit(b, "same"))
        assert first["task_id"] == second["task_id"]
        identifier = first["task_id"]
        status = await call(a, "get_service_status")
        assert status["host_count"] == 2
        assert status["pid"] == discovery["pid"] and child.poll() is None
        # A separately owned raw stdio process can be forcibly stopped without killing backend.
        front = await asyncio.to_thread(
            subprocess.Popen,
            [sys.executable, "-m", "zhenzhen_seedance_video", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            front.stdin.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-11-25",
                            "capabilities": {},
                            "clientInfo": {"name": "synthetic", "version": "1"},
                        },
                    }
                )
                + "\n"
            )
            front.stdin.flush()
            line = await asyncio.wait_for(asyncio.to_thread(front.stdout.readline), 5)
            assert json.loads(line)["result"]
            # The backend was started separately; this frontend has no owned children.
            # Popen.kill uses its retained Windows process handle, not WMI/taskkill
            # enumeration or a possibly reused PID.
            await asyncio.to_thread(front.kill)
            await asyncio.to_thread(front.wait, timeout=5)
        finally:
            if front.poll() is None:
                front.stdin.close()
                await asyncio.to_thread(front.wait, timeout=5)
            if not front.stdin.closed:
                front.stdin.close()
            front.stdout.close()
        assert (await call(b, "get_service_status"))["pid"] == status["pid"]
        # A conflicting frontend is refused, without affecting existing clients.
        monkeypatch.setenv("ZHENZHEN_SEEDANCE_GENERATION_CONCURRENCY", "9")
        with pytest.raises(BaseExceptionGroup):
            async with protocol():
                pass
        monkeypatch.delenv("ZHENZHEN_SEEDANCE_GENERATION_CONCURRENCY")
        assert (await call(b, "get_service_status"))["pid"] == status["pid"]
        http.responses.append((200, {}, video()))
        (control / "complete").touch()
        for _ in range(30):
            row = await call(b, "get_task", task_id=identifier)
            if row["delivery"] == "ready":
                break
            await asyncio.sleep(0.1)
        assert row["delivery"] == "ready"
        artifact = (await call(b, "list_artifacts", task_id=identifier))["items"][0]
        copied = await call(
            b,
            "copy_artifact",
            artifact_id=artifact["artifact_id"],
            target_path=str(tmp_path / "delivered.mp4"),
        )
        assert copied["copied"]
        assert (
            hashlib.sha256((tmp_path / "delivered.mp4").read_bytes()).hexdigest()
            == artifact["sha256"]
        )
        assert len((control / "posts.jsonl").read_text().splitlines()) == 1
    async with protocol() as reconnected:
        assert (await call(reconnected, "get_service_status"))["pid"] == status["pid"]
    await asyncio.to_thread(child.wait, timeout=10)
    assert child.returncode == 0


@pytest.mark.parametrize(
    "phase",
    ["prepare", "submitted", "after_id", "download_before_publish", "download_after_publish"],
)
async def test_real_backend_crash_restart_by_phase(backend, phase):
    start, control, http, _ = backend
    child = await start(phase)
    if phase.startswith("download"):
        http.responses.append((200, {}, video()))
        (control / "complete").touch()
    async with protocol() as session:
        accepted = await submit(session, "crash-test")
        await until(lambda: child.poll() is not None)
        assert child.returncode == 91
    await start(phase)
    async with protocol() as session:
        found = await call(session, "find_task_by_request_key", request_key="crash-test")
        assert found["task_id"] == accepted["task_id"]
        if phase == "submitted":
            row = await call(session, "get_task", task_id=found["task_id"])
            assert row["remote_state"] == "unknown" and row["generation_slot_held"] == 1
            assert row["auto_mode"] == "needs_attention"
        else:
            if phase != "download_after_publish":
                http.responses.append((200, {}, video()))
            (control / "complete").touch()
            for _ in range(50):
                row = await call(session, "get_task", task_id=found["task_id"])
                if row["delivery"] == "ready":
                    break
                await asyncio.sleep(0.1)
            assert row["delivery"] == "ready"
        assert len((control / "posts.jsonl").read_text().splitlines()) == 1


async def test_storage_fault_protects_then_reconciles_in_child(backend):
    start, control, http, _ = backend
    await start("storage")
    async with protocol() as a, protocol() as b:
        first = await submit(a, "before-fault")
        await until(lambda: (control / "fault").exists())
        assert (await call(b, "get_service_status"))["storage_fault"]
        rejected = await submit(b, "during-fault")
        assert rejected["ok"] is False
        assert len((control / "posts.jsonl").read_text().splitlines()) == 1
        http.responses.append((200, {}, video()))
        (control / "complete").touch()
        (control / "repair").touch()
        for _ in range(40):
            row = await call(b, "get_task", task_id=first["task_id"])
            if row["delivery"] == "ready":
                break
            await asyncio.sleep(0.1)
        assert row["delivery"] == "ready"
        assert not (await call(b, "get_service_status"))["storage_fault"]
