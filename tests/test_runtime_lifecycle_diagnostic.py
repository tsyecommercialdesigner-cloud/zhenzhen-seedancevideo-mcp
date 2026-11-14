"""Observe isolated Windows backend processes, ownership and lease transitions."""

import asyncio
import json
import time

import pytest
import win32api
import win32con
import win32event
import win32process
from test_runtime import runtime_environment as runtime_environment

from zhenzhen_seedance_video.ownership import OwnershipError, StableLock
from zhenzhen_seedance_video.runtime import connect_or_start


async def test_process_lifetimes_owner_lock_and_host_leases(runtime_environment):
    events = []
    handles = []
    clients = []

    def event(name, **values):
        events.append({"event": name, "monotonic": round(time.monotonic(), 6), **values})

    async def close(client):
        await client.close()
        clients.remove(client)

    try:
        previous = None
        previous_exit = None
        for cycle in range(3):
            if cycle == 1:
                startup = StableLock(runtime_environment, "startup.lock").acquire()
                pending = [
                    asyncio.create_task(connect_or_start(startup_timeout=10)) for _ in range(2)
                ]
                try:
                    await asyncio.sleep(0.2)
                    assert all(not task.done() for task in pending)
                    event("startup_lock_blocks_both", cycle=cycle)
                finally:
                    startup.close()
                client, concurrent = await asyncio.gather(*pending)
                clients.extend((client, concurrent))
                assert client.instance_id == concurrent.instance_id
                event("concurrent_clients_shared_instance", cycle=cycle)
                await close(concurrent)
            else:
                client = await connect_or_start(startup_timeout=10)
                clients.append(client)
            record = json.loads((runtime_environment / "discovery.json").read_text())
            handle = win32api.OpenProcess(
                win32con.SYNCHRONIZE | 0x1000,
                False,
                record["pid"],
            )
            handles.append(handle)
            status = await client.call("get_service_status")
            assert status["execution_mode"] == "local"
            assert status["pid"] == record["pid"]
            if previous is not None:
                assert win32event.WaitForSingleObject(previous, 0) == win32event.WAIT_OBJECT_0
                assert win32process.GetProcessTimes(handle)["CreationTime"] >= previous_exit
            event(
                "connected",
                cycle=cycle,
                pid=record["pid"],
                created_at=record["created_at"],
                hosts=status["host_count"],
            )
            with pytest.raises(OwnershipError, match="LOCK_BUSY"):
                StableLock(runtime_environment, "owner.lock").acquire()
            event("owner_lock_busy", cycle=cycle)

            if cycle == 0:
                other = await connect_or_start(startup_timeout=10)
                clients.append(other)
                assert other.instance_id == client.instance_id
                assert (await other.call("get_service_status"))["host_count"] == 2
                event("second_host_joined", cycle=cycle, hosts=2)
                await close(client)
                await asyncio.sleep(0.1)
                status = await other.call("get_service_status")
                assert status["host_count"] == 1
                event("first_host_left", cycle=cycle, hosts=1)
                await close(other)
                event("last_host_left", cycle=cycle)
                # Rejoin during the configured one-second grace period.
                client = await connect_or_start(startup_timeout=10)
                clients.append(client)
                assert client.instance_id == other.instance_id
                event("grace_rejoined", cycle=cycle)

            await close(client)
            event("last_host_left", cycle=cycle)
            result = await asyncio.to_thread(win32event.WaitForSingleObject, handle, 10000)
            assert result == win32event.WAIT_OBJECT_0
            previous_exit = win32process.GetProcessTimes(handle)["ExitTime"]
            event(
                "process_exited", cycle=cycle, pid=record["pid"], exit_at=previous_exit.isoformat()
            )
            with StableLock(runtime_environment, "owner.lock"):
                event("owner_lock_free", cycle=cycle)
            previous = handle
        print("LIFECYCLE_TRACE=" + json.dumps(events, separators=(",", ":")), flush=True)
    finally:
        for client in clients:
            await client.close()
        for handle in handles:
            handle.Close()
