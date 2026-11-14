import asyncio
import json
import os
import subprocess
import sys

import pytest
import win32api
import win32con
import win32job
import win32process
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from zhenzhen_seedance_video.config import load_configuration
from zhenzhen_seedance_video.ownership import OwnershipError, ProcessIdentity, confirm_exited
from zhenzhen_seedance_video.rpc import read_frame, write_frame
from zhenzhen_seedance_video.runtime import connect_or_start
from zhenzhen_seedance_video.storage import Database


@pytest.fixture
def runtime_environment(monkeypatch, tmp_path, network_guard):
    for key, value in {
        "API_KEY": "synthetic-no-provider",
        "HEARTBEAT_SECONDS": "1",
        "LEASE_TIMEOUT_SECONDS": "3",
        "SHUTDOWN_GRACE_SECONDS": "1",
        "SHUTDOWN_DRAIN_SECONDS": "1",
    }.items():
        monkeypatch.setenv("ZHENZHEN_SEEDANCE_" + key, value)
    # Discovery ports are dynamically assigned by an isolated child process.
    # Register only the verified loopback port before the client opens it.
    import zhenzhen_seedance_video.runtime as runtime

    original = runtime._connect

    async def connect(directory, record, explicit):
        network_guard.add(record["port"])
        return await original(directory, record, explicit)

    monkeypatch.setattr(runtime, "_connect", connect)
    return tmp_path / "local-app-data/ZhenzhenSeedanceVideo/runtime"


async def wait_exit(identity):
    for _ in range(100):
        try:
            confirm_exited(identity)
            return
        except OwnershipError as error:
            assert str(error) == "OLD_PROCESS_STILL_ALIVE"
            await asyncio.sleep(0.05)
    pytest.fail("Isolated backend did not exit within bounded shutdown")


async def test_hidden_backend_two_clients_and_restart(runtime_environment):
    a = await connect_or_start(startup_timeout=10)
    b = None
    try:
        first = await a.call("get_service_status")
        b = await connect_or_start(startup_timeout=10)
        second = await b.call("get_service_status")
        assert a.instance_id == b.instance_id
        assert first["pid"] == second["pid"]
        assert second["host_count"] == 2
        await a.close()
        await asyncio.sleep(0.1)
        assert (await b.call("get_service_status"))["host_count"] == 1
        record = json.loads((runtime_environment / "discovery.json").read_text())
    finally:
        await a.close()
        if b:
            await b.close()
    await wait_exit(ProcessIdentity(record["pid"], record["created_at"]))


async def test_grace_reconnect_and_expired_client(runtime_environment):
    a = await connect_or_start(startup_timeout=10)
    instance = a.instance_id
    await a.close()
    b = await connect_or_start(startup_timeout=10)
    try:
        assert b.instance_id == instance
        record = json.loads((runtime_environment / "discovery.json").read_text())
        reader, writer = await asyncio.open_connection("127.0.0.1", record["port"])
        token = (runtime_environment / "rpc-token").read_text()
        await write_frame(writer, {"protocol": 1, "token": token}, 8388608)
        assert (await read_frame(reader, 8388608))["ok"]
    finally:
        await b.close()
    assert await asyncio.wait_for(reader.read(1), 5) == b""
    writer.close()
    await writer.wait_closed()
    await wait_exit(ProcessIdentity(record["pid"], record["created_at"]))


async def test_sdk_v2_stdio_frontend_connects_shared_backend(runtime_environment):
    backend = await connect_or_start(startup_timeout=10)
    try:
        expected = await backend.call("get_service_status")
        environment = {
            key: value
            for key, value in os.environ.items()
            if key.startswith("ZHENZHEN_SEEDANCE_") or key in {"LOCALAPPDATA", "PYTHONPATH"}
        }
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "zhenzhen_seedance_video", "stdio"], env=environment
        )
        async with stdio_client(params) as streams:
            async with ClientSession(streams[0], streams[1], read_timeout_seconds=10) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert "get_service_status" in [tool.name for tool in tools.tools]
                result = await session.call_tool("get_service_status", {})
                assert not result.is_error
                assert str(expected["pid"]) in str(result)
                policy = await session.call_tool(
                    "set_prompt_optimization_policy",
                    {
                        "enabled": True,
                        "expected_version": 0,
                        "confirmed": True,
                    },
                )
                assert policy.structured_content["enabled"] is True
                submitted = await session.call_tool(
                    "submit_video",
                    {
                        "request_key": "stdio-intake",
                        "request": {
                            "model": "seedance-2.0-mini-t2v",
                            "prompt": "synthetic fox",
                        },
                    },
                )
                accepted = submitted.structured_content
                assert accepted["accepted"] is True
                assert accepted["authorization"]["source"] == "always_allow"
                found = await backend.call(
                    "find_task_by_request_key", {"request_key": "stdio-intake"}
                )
                assert found.pop("stale") is False
                assert found == accepted
                source = runtime_environment.parent / "synthetic-input.png"
                source.write_bytes(b"synthetic-local-material")
                received = await session.call_tool(
                    "submit_video",
                    {
                        "request_key": "stdio-material",
                        "request": {
                            "model": "seedance-2.0-mini-i2v",
                            "prompt": "synthetic",
                            "images": [{"local_path": str(source)}],
                        },
                    },
                )
                local = received.structured_content
                material_id = local["materials"][0]["material_id"]
                (runtime_environment.parent / "materials" / (material_id + ".input")).unlink()
                repaired = await session.call_tool(
                    "repair_task_materials",
                    {
                        "task_id": local["task_id"],
                        "material_id": material_id,
                        "source": str(source),
                        "expected_version": local["version"],
                    },
                )
                assert repaired.structured_content["version"] == 2
        record = json.loads((runtime_environment / "discovery.json").read_text())
        assert (await backend.call("get_service_status"))["pid"] == expected["pid"]
    finally:
        await backend.close()
    await wait_exit(ProcessIdentity(record["pid"], record["created_at"]))
    restarted = await connect_or_start(startup_timeout=10)
    try:
        assert restarted.instance_id != backend.instance_id
        found = await restarted.call("find_task_by_request_key", {"request_key": "stdio-intake"})
        assert found.pop("stale") is False
        assert found == accepted
        assert (await restarted.call("get_prompt_optimization_policy"))["enabled"] is True
        record = json.loads((runtime_environment / "discovery.json").read_text())
    finally:
        await restarted.close()
    await wait_exit(ProcessIdentity(record["pid"], record["created_at"]))


@pytest.mark.parametrize("allow_breakaway", [True, False])
async def test_real_job_object_exit_and_incompatible_job(runtime_environment, allow_breakaway):
    script = """
import asyncio,json,sys,uuid,win32api,win32job
from zhenzhen_seedance_video.runtime import connect_or_start, RuntimeErrorCode
job_name='seedance-test-'+uuid.uuid4().hex
job=win32job.CreateJobObject(None,job_name)
limits=win32job.QueryInformationJobObject(job,win32job.JobObjectExtendedLimitInformation)
flags=win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
if sys.argv[1]=='yes': flags |= win32job.JOB_OBJECT_LIMIT_BREAKAWAY_OK
limits['BasicLimitInformation']['LimitFlags']=flags
win32job.SetInformationJobObject(job,win32job.JobObjectExtendedLimitInformation,limits)
win32job.AssignProcessToJobObject(job,win32api.GetCurrentProcess())
async def main():
    try:
        client=await connect_or_start(startup_timeout=10)
    except RuntimeErrorCode as error:
        print(json.dumps({'error':str(error)}),flush=True)
    else:
        result=(await client.call('get_service_status'))|{'job_name':job_name}
        print(json.dumps(result),flush=True)
        await asyncio.to_thread(sys.stdin.readline)
        job.Close()
asyncio.run(main())
"""
    process = await asyncio.to_thread(
        subprocess.Popen,
        [sys.executable, "-c", script, "yes" if allow_breakaway else "no"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW | win32process.CREATE_BREAKAWAY_FROM_JOB,
    )
    b = None
    record = None
    try:
        line = await asyncio.wait_for(asyncio.to_thread(process.stdout.readline), 15)
        assert line, process.stderr.read()
        result = json.loads(line)
        if not allow_breakaway:
            assert result["error"] == "BACKEND_LAUNCH_OR_JOB_INCOMPATIBLE"
            assert not (runtime_environment / "discovery.json").exists()
        else:
            b = await connect_or_start(startup_timeout=10)
            record = json.loads((runtime_environment / "discovery.json").read_text())
            handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, result["pid"])
            host_job = win32job.OpenJobObject(win32job.JOB_OBJECT_QUERY, False, result["job_name"])
            try:
                assert not win32job.IsProcessInJob(handle, host_job)
            finally:
                host_job.Close()
                handle.Close()
            await asyncio.to_thread(process.communicate, "\n", timeout=10)
            assert (await b.call("get_service_status"))["pid"] == result["pid"]
    finally:
        if process.poll() is None:
            await asyncio.to_thread(process.communicate, "\n", timeout=10)
        if b:
            await b.close()
        if record:
            await wait_exit(ProcessIdentity(record["pid"], record["created_at"]))


async def test_restart_keeps_unknown_intent_and_quota(runtime_environment):
    configuration = load_configuration()
    database = Database(configuration.state_dir)

    def seed(c):
        c.execute("""INSERT INTO tasks(task_id,request_key,api_id,model,kind,rule_version,
          intent_digest,effective_parameters,output_dir,connection_binding,created_at,
          generation_slot_held,stage,remote_state)
          VALUES ('t','r','seedance-video','synthetic','t2v','1','hash','{}',
          'D:\\test','binding','now',1,'submitting','unknown')""")
        c.execute("""INSERT INTO attempts(attempt_id,task_id,phase,round,epoch,state,
          started_at,remaining_budget,effect_started)
          VALUES ('a','t','submit',1,0,'intent','now',0,1)""")

    await database.execute(seed)
    await database.close()
    versions = []
    for _ in range(2):
        client = await connect_or_start(startup_timeout=10)
        try:
            status = await client.call("get_service_status")
            assert status["generation_slots_held"] == 1
            record = json.loads((runtime_environment / "discovery.json").read_text())
        finally:
            await client.close()
        await wait_exit(ProcessIdentity(record["pid"], record["created_at"]))
        database = Database(configuration.state_dir)
        try:
            row = await database.execute(
                lambda c: dict(c.execute("SELECT * FROM tasks").fetchone()), write=False
            )
            assert row["remote_state"] == "unknown"
            assert row["auto_mode"] == "needs_attention"
            assert row["generation_slot_held"] == 1
            versions.append(row["version"])
            assert len(await database.pending_intents()) == 1
        finally:
            await database.close()
    assert versions == [2, 2]
