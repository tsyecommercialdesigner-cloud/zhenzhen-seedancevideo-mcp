"""Bounded diagnostic of the installed Windows venv launcher's own Job.

These tests deliberately terminate only a newly created isolated launcher.
They establish a mechanism, not the historical cause of a Desktop exit.
"""

import asyncio
import ctypes
import json
import os
import uuid

import pytest
import win32api
import win32con
import win32event
import win32job
import win32process
from test_runtime import runtime_environment as runtime_environment

from zhenzhen_seedance_video.ownership import StableLock
from zhenzhen_seedance_video.runtime import connect_or_start


class HandleEntry(ctypes.Structure):
    _fields_ = [
        ("object", ctypes.c_void_p),
        ("pid", ctypes.c_size_t),
        ("handle", ctypes.c_size_t),
        ("access", ctypes.c_ulong),
        ("trace", ctypes.c_ushort),
        ("type_index", ctypes.c_ushort),
        ("attributes", ctypes.c_ulong),
        ("reserved", ctypes.c_ulong),
    ]


def launcher_job(launcher, launcher_pid, backend):
    """Select by per-handle membership, never by hidden kernel object address."""
    sentinel = win32job.CreateJobObject(None, "seedance-final-probe-" + uuid.uuid4().hex)
    try:
        query = ctypes.WinDLL("ntdll").NtQuerySystemInformation
        query.argtypes = [ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p]
        query.restype = ctypes.c_long
        size = 1024 * 1024
        for _ in range(8):
            buffer = ctypes.create_string_buffer(size)
            needed = ctypes.c_ulong()
            result = query(64, buffer, size, ctypes.byref(needed))
            if result == 0:
                break
            assert result & 0xFFFFFFFF == 0xC0000004, hex(result & 0xFFFFFFFF)
            size = max(size * 2, needed.value + 4096)
        else:
            pytest.fail("System handle snapshot exceeded bounded capacity")
        count = ctypes.c_size_t.from_buffer(buffer).value
        offset = 2 * ctypes.sizeof(ctypes.c_size_t)
        assert offset + count * ctypes.sizeof(HandleEntry) <= size
        entries = (HandleEntry * count).from_buffer(buffer, offset)
        job_type = next(
            item.type_index
            for item in entries
            if item.pid == os.getpid() and item.handle == int(sentinel)
        )
        matches = []
        try:
            for entry in entries:
                if entry.pid != launcher_pid or entry.type_index != job_type:
                    continue
                duplicate = win32api.DuplicateHandle(
                    launcher,
                    entry.handle,
                    win32api.GetCurrentProcess(),
                    0,
                    False,
                    win32con.DUPLICATE_SAME_ACCESS,
                )
                try:
                    if win32job.IsProcessInJob(backend, duplicate):
                        info = win32job.QueryInformationJobObject(
                            duplicate, win32job.JobObjectExtendedLimitInformation
                        )
                        matches.append((duplicate, info["BasicLimitInformation"]["LimitFlags"]))
                        duplicate = None
                finally:
                    if duplicate is not None:
                        duplicate.Close()
            assert len(matches) == 1, "Expected exactly one launcher-held Job containing backend"
            return matches.pop()
        finally:
            for handle, _ in matches:
                handle.Close()
    finally:
        sentinel.Close()


@pytest.mark.parametrize("mode", ["no_extra_handle", "hold_then_release", "hold_then_grace"])
async def test_launcher_job_lifetime(runtime_environment, mode):
    client = await connect_or_start(startup_timeout=10)
    launcher = backend = held_job = None
    evidence = {"mode": mode}
    try:
        status = await client.call("get_service_status")
        assert status["execution_mode"] == "local" and not status["dispatch_allowed"]
        start = json.loads((runtime_environment / "starting.json").read_text())
        record = json.loads((runtime_environment / "discovery.json").read_text())
        assert start["launch_id"] == record["launch_id"]
        assert start["pid"] != record["pid"], "This diagnostic requires a venv launcher"
        access = win32con.SYNCHRONIZE | win32con.PROCESS_TERMINATE | 0x1000
        launcher = win32api.OpenProcess(access | win32con.PROCESS_DUP_HANDLE, False, start["pid"])
        backend = win32api.OpenProcess(access, False, record["pid"])
        assert (
            win32process.GetProcessTimes(launcher)["CreationTime"].isoformat()
            == start["created_at"]
        )
        assert (
            win32process.GetProcessTimes(backend)["CreationTime"].isoformat()
            == record["created_at"]
        )
        held_job, flags = launcher_job(launcher, start["pid"], backend)
        assert flags & win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        assert not win32job.IsProcessInJob(launcher, held_job)
        evidence.update(launcher=start["pid"], backend=record["pid"], flags=hex(flags))
        if mode == "no_extra_handle":
            held_job.Close()
            held_job = None
        # Retained handle + verified creation time restrict termination to this test launcher.
        win32process.TerminateProcess(launcher, 73)
        assert await asyncio.to_thread(win32event.WaitForSingleObject, launcher, 5000) == 0
        if mode != "no_extra_handle":
            await asyncio.sleep(0.2)
            assert win32event.WaitForSingleObject(backend, 0) == win32event.WAIT_TIMEOUT
            after = await client.call("get_service_status")
            assert after["pid"] == record["pid"] and after["host_count"] == 1
            evidence["rpc_alive_with_extra_handle"] = True
            if mode == "hold_then_release":
                held_job.Close()
                held_job = None
            else:
                await client.close()
        assert await asyncio.to_thread(win32event.WaitForSingleObject, backend, 10000) == 0
        evidence["backend_exit_code"] = win32process.GetExitCodeProcess(backend)
        evidence["backend_exit_at"] = win32process.GetProcessTimes(backend)["ExitTime"].isoformat()
        evidence["job_still_held_at_exit"] = held_job is not None
        with StableLock(runtime_environment, "owner.lock"):
            evidence["owner_lock_released"] = True
        print("LAUNCHER_JOB_TRACE=" + json.dumps(evidence), flush=True)
    finally:
        await client.close()
        if held_job is not None:
            held_job.Close()
        # Bounded failure cleanup uses only this test's retained process handles.
        for handle in (backend, launcher):
            if handle is not None:
                if await asyncio.to_thread(win32event.WaitForSingleObject, handle, 5000) != 0:
                    win32process.TerminateProcess(handle, 74)
                    await asyncio.to_thread(win32event.WaitForSingleObject, handle, 5000)
                handle.Close()
