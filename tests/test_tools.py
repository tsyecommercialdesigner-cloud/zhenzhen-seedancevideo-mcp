import asyncio
import json
import os
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from test_artifacts import video
from test_scheduler import SyntheticAdapter

from zhenzhen_seedance_video.admission import AdmissionService
from zhenzhen_seedance_video.artifacts import ArtifactService
from zhenzhen_seedance_video.cleanup import CleanupService
from zhenzhen_seedance_video.config import load_configuration
from zhenzhen_seedance_video.diagnostics import Diagnostics
from zhenzhen_seedance_video.network import NetworkPolicy, origin
from zhenzhen_seedance_video.provider_response import decode_response
from zhenzhen_seedance_video.rpc import RPCServer
from zhenzhen_seedance_video.scheduler import Scheduler
from zhenzhen_seedance_video.storage import Database
from zhenzhen_seedance_video.task_state import _change, _load
from zhenzhen_seedance_video.tools import READ_ONLY, TOOL_NAMES, Tools


@pytest.fixture
async def surface(monkeypatch, fake_http):
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_API_KEY", "synthetic")
    config = load_configuration()
    db = Database(config.state_dir)
    network = NetworkPolicy(config, _test_origins=[origin(fake_http.url)])
    admission = AdmissionService(db, config, "binding")
    artifacts = ArtifactService(db, config, network)
    cleanup = CleanupService(db, config)
    adapter = SyntheticAdapter()
    leases = SimpleNamespace(dispatch_allowed=True, network_allowed=True, hosts={})
    scheduler = Scheduler(db, config, "binding", adapter, leases=leases, delivery=artifacts)
    diagnostics = Diagnostics(config.root / "diagnostics", secrets=(config.api_key,))
    facade = Tools(
        admission, artifacts, cleanup, scheduler=scheduler, leases=leases, diagnostics=diagnostics
    )
    server = RPCServer(config, facade.handlers())
    await server.start()
    server.publish_discovery(config.root / "runtime")
    try:
        yield facade, adapter, fake_http
    finally:
        await server.close()
        await scheduler.close()
        await cleanup.close()
        await artifacts.close()
        await admission.close()
        diagnostics.close()
        await network.close()
        await db.close()


@asynccontextmanager
async def protocol():
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.startswith("ZHENZHEN_SEEDANCE_") or key in {"LOCALAPPDATA", "PYTHONPATH"}
    }
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "zhenzhen_seedance_video", "stdio"], env=environment
    )
    async with stdio_client(params) as streams:
        async with ClientSession(*streams, read_timeout_seconds=10) as session:
            await session.initialize()
            yield session


async def call(session, name, **arguments):
    result = await session.call_tool(name, arguments)
    assert not result.is_error, result
    assert result.structured_content is not None, result
    return result.structured_content


async def submit(session, key="test"):
    return await call(
        session,
        "submit_video",
        request_key=key,
        request={"model": "seedance-2.0-mini-t2v", "prompt": "synthetic fox"},
    )


async def test_mcp_observed_and_legacy_raw_status(surface):
    facade, _, _ = surface
    fixture = Path(__file__).parent / "fixtures/provider/live-observed/query-success-usage.json"
    observation = decode_response(
        fixture.read_bytes(),
        expected_model="seedance-2.0-mini-t2v",
        expected_id="task_live_probe_01",
    )
    async with protocol() as session:
        task = await submit(session, "observed-status")
        tid = task["task_id"]
        await facade.scheduler.state.observe(tid, observation, operation_epoch=0, now=1)
        result = await call(session, "get_task", task_id=tid)
        assert (result["raw_status"], result["normalized_status"], result["remote_state"]) == (
            "SUCCESS",
            "completed",
            "succeeded",
        )
        assert "example.invalid" not in json.dumps(result)
        supplied = json.loads(
            (fixture.parent.parent / "user-supplied/query-completed.json").read_bytes()
        )
        supplied["id"] = "task_live_probe_01"  # Keep the accepted remote identity.
        completed = decode_response(
            json.dumps(supplied).encode(),
            expected_model="seedance-2.0-mini-t2v",
            expected_id="task_live_probe_01",
        )
        await facade.scheduler.state.observe(tid, completed, operation_epoch=0, now=2)
        result = await call(session, "get_task", task_id=tid)
        assert result["raw_status"] == result["normalized_status"] == "completed"
        db = facade.scheduler.db
        for facts in ("{}", '{"provider_status":"Bearer secret"}'):
            await db.execute(
                lambda c, facts=facts: c.execute(
                    "UPDATE remote_observations SET facts=? WHERE task_id=?", (facts, tid)
                )
            )
            legacy = await call(session, "get_task", task_id=tid)
            assert legacy["raw_status"] is None and legacy["normalized_status"] == "completed"
            assert "secret" not in json.dumps(legacy)


async def test_full_agent_workflow_and_all_tool_schemas(surface, tmp_path):
    facade, adapter, http = surface
    async with protocol() as session:
        tools = (await session.list_tools()).tools
        assert {t.name for t in tools} == set(TOOL_NAMES)
        for tool in tools:
            assert tool.output_schema
            assert tool.annotations.read_only_hint == (tool.name in READ_ONLY)
        assert (await call(session, "get_capabilities"))["apis"][0]["model_count"] == 26
        assert (
            await call(
                session,
                "get_capabilities",
                api_id="seedance-video",
                model_id="seedance-2.0-mini-t2v",
            )
        )["operations"]["success_envelope"] == "observed_partial"
        pre = await call(
            session,
            "preflight_video_task",
            request={"model": "seedance-2.0-mini-t2v", "prompt": "secret prompt"},
        )
        assert pre["authorization"]["enabled"] is False
        assert "secret prompt" not in json.dumps(pre)
        policy = await call(session, "get_prompt_optimization_policy")
        await call(
            session,
            "set_prompt_optimization_policy",
            enabled=True,
            expected_version=policy["version"],
            confirmed=True,
        )
        task = await submit(session)
        identifier = task["task_id"]
        assert (await call(session, "find_task_by_request_key", request_key="test"))[
            "task_id"
        ] == identifier
        assert (await call(session, "get_task", task_id=identifier))["authorization"][
            "source"
        ] == "always_allow"
        await facade.scheduler.dispatch()
        adapter.query_failure = True
        for _ in range(6):
            await facade.scheduler.query(identifier, explicit=True)
        row = await call(session, "get_task", task_id=identifier)
        await call(
            session, "resume_task_tracking", task_id=identifier, expected_version=row["version"]
        )
        adapter.query_failure = False
        adapter.status = "completed"
        refreshed = await call(session, "refresh_task", task_id=identifier)
        assert refreshed["remote_state"] == "succeeded"
        artifact = (
            await facade.artifacts.register(
                identifier, [{"url": http.url + "/video?signature=private"}]
            )
        )[0]
        http.responses.append((200, {}, video()))
        await facade.artifacts.download(artifact)
        item = (await call(session, "list_artifacts", task_id=identifier))["items"][0]
        assert item["state"] == "ready"
        assert (await call(session, "verify_artifact", artifact_id=artifact))["state"] == "ready"
        copied = await call(
            session,
            "copy_artifact",
            artifact_id=artifact,
            target_path="out.mp4",
            workspace_root=str(tmp_path / "work"),
        )
        assert copied["copied"]
        assert (tmp_path / "work/out.mp4").read_bytes() == video()
        final = await call(session, "get_task", task_id=identifier)
        assert final["charge"]["amount"] is None
        assert "signature" not in json.dumps(final)
        assert (
            await call(
                session,
                "wait_task",
                task_id=identifier,
                after_version=task["version"],
                timeout_seconds=0,
            )
        )["wait_timed_out"] is False
        assert len(adapter.posts) == 1
        assert (await call(session, "get_service_status"))["generation_slots_held"] == 0
        up = await call(
            session,
            "upscale_video",
            request_key="upscale",
            request={
                "model": "zhenzhen-upscaler",
                "metadata": {
                    "content": [
                        {
                            "type": "video_url",
                            "video_url": {"url": "https://synthetic.example/source.mp4"},
                        }
                    ]
                },
            },
        )
        assert up["accepted"]
        cancelled = await call(
            session, "cancel_task", task_id=up["task_id"], expected_version=up["version"]
        )
        assert cancelled["locally_cancelled"]
        for name, args in {
            "retry_unsubmitted_task": {"task_id": identifier, "expected_version": final["version"]},
            "repair_task_materials": {
                "task_id": identifier,
                "material_id": "missing",
                "source": str(tmp_path / "missing"),
                "expected_version": final["version"],
            },
            "retry_material_cleanup": {"task_id": identifier, "expected_version": final["version"]},
            "retry_task_download": {"task_id": identifier, "expected_version": final["version"]},
        }.items():
            result = await call(session, name, **args)
            assert result is not None
        abandoned = await call(
            session,
            "abandon_task",
            task_id=up["task_id"],
            expected_version=cancelled["version"],
            reason="user decision",
            acknowledge_remote_may_continue=True,
        )
        assert abandoned["auto_mode"] == "abandoned"
        failure = await call(session, "get_task", task_id="missing")
        diagnostic = await call(
            session, "get_diagnostic", diagnostic_id=failure["diagnostic"]["diagnostic_id"]
        )
        assert diagnostic["diagnostic_id"]
        assert (await call(session, "list_tasks"))["items"]


async def test_two_clients_pagination_wait_and_exception_visibility(surface):
    facade, _, _ = surface
    async with protocol() as a, protocol() as b:
        tasks = [await submit(a, str(i)) for i in range(3)]
        identifier = tasks[0]["task_id"]

        def change(c):
            return _change(
                c,
                _load(c, identifier),
                {"attention": '["QUERY_RETRIES_EXHAUSTED"]', "auto_mode": "needs_attention"},
                kind="test",
                now="later",
            )

        await facade.db.execute(change)
        for session in (a, b):
            assert len((await call(session, "list_tasks", needs_attention=True))["items"]) == 1
        first = await call(a, "list_tasks", limit=1)
        second = await call(b, "list_tasks", limit=1, cursor=first["next_cursor"])
        assert second["items"][0]["task_id"] == tasks[1]["task_id"]
        invalid = await call(
            b, "list_tasks", limit=1, cursor=first["next_cursor"], needs_attention=True
        )
        assert invalid["ok"] is False
        waited = await call(a, "wait_task", task_id=identifier, after_version=1, timeout_seconds=1)
        assert waited["version"] == 2 and not waited["wait_timed_out"]
        await facade.db.execute(
            lambda c: c.execute(
                "UPDATE tasks SET last_observed_at='timestamp-only' WHERE task_id=?", (identifier,)
            )
        )
        waited = await call(
            a, "wait_task", task_id=identifier, after_version=2, timeout_seconds=0.1
        )
        assert waited["wait_timed_out"]
        await facade.db.execute(
            lambda c: _change(
                c, _load(c, identifier), {"attention": "[]"}, kind="resolved", now="later"
            )
        )
        assert not (await call(b, "list_tasks", needs_attention=True))["items"]
        invalid = await call(
            a, "wait_task", task_id=identifier, after_version=2, timeout_seconds=31
        )
        assert invalid["ok"] is False


async def test_local_queries_provider_gate_and_sanitized_errors(surface, monkeypatch):
    facade, _, _ = surface
    facade.scheduler = None
    async with protocol() as session:
        task = await submit(session)
        unavailable = await call(session, "refresh_task", task_id=task["task_id"])
        assert unavailable["error"] == "CAPABILITY_UNVERIFIED"
        facade.db._fault.set()
        assert (await call(session, "get_task", task_id=task["task_id"]))["stale"]
        assert (await call(session, "get_service_status"))["storage_fault"]
        facade.db._fault.clear()

        async def fail(task_id):
            raise RuntimeError("Traceback API_KEY=synthetic https://secret/?token=private " * 1000)

        monkeypatch.setattr(facade.queries, "get", fail)
        result = await call(session, "get_task", task_id=task["task_id"])
        assert result["error"] == "INTERNAL_ERROR"
        assert not any(word in json.dumps(result) for word in ("Traceback", "private", "API_KEY"))


async def test_protocol_cancellation_and_committed_management(surface, monkeypatch):
    facade, _, _ = surface
    accepted = asyncio.Event()
    release = asyncio.Event()
    original = facade.admission.submit

    async def delayed(*args, **kwargs):
        result = await original(*args, **kwargs)
        accepted.set()
        await release.wait()
        return result

    monkeypatch.setattr(facade.admission, "submit", delayed)
    async with protocol() as a, protocol() as b:
        submitting = asyncio.create_task(submit(a, "cancel-waiter"))
        await asyncio.wait_for(accepted.wait(), 5)
        submitting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await submitting
        release.set()
        found = await call(b, "find_task_by_request_key", request_key="cancel-waiter")
        assert found["accepted"] and not found["locally_cancelled"]
        identifier = found["task_id"]
        waiting = asyncio.create_task(
            call(
                a,
                "wait_task",
                task_id=identifier,
                after_version=found["version"],
                timeout_seconds=30,
            )
        )
        await asyncio.sleep(0.1)
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        committed = asyncio.Event()
        finish = asyncio.Event()
        cancel = facade.state.cancel_unsubmitted

        async def lost(*args, **kwargs):
            result = await cancel(*args, **kwargs)
            committed.set()
            await finish.wait()
            return result

        monkeypatch.setattr(facade.state, "cancel_unsubmitted", lost)
        operation = asyncio.create_task(
            call(a, "cancel_task", task_id=identifier, expected_version=found["version"])
        )
        await asyncio.wait_for(committed.wait(), 5)
        operation.cancel()
        with pytest.raises(asyncio.CancelledError):
            await operation
        finish.set()
        current = await call(b, "get_task", task_id=identifier)
        assert current["locally_cancelled"] and current["version"] > found["version"]


async def test_duplicate_resume_and_conflict_over_protocol(surface):
    facade, _, _ = surface
    async with protocol() as a, protocol() as b:
        task = await submit(a)
        identifier = task["task_id"]
        await facade.scheduler.dispatch()
        row = await call(a, "get_task", task_id=identifier)
        abandoned = await call(
            a,
            "abandon_task",
            task_id=identifier,
            expected_version=row["version"],
            reason="pause tracking",
            acknowledge_remote_may_continue=True,
        )
        results = await asyncio.gather(
            *(
                call(
                    s,
                    "resume_task_tracking",
                    task_id=identifier,
                    expected_version=abandoned["version"],
                )
                for s in (a, b)
            )
        )
        assert results[0]["version"] == results[1]["version"]
        assert results[0]["generation_slot_held"] == 1
        rounds = await facade.db.execute(
            lambda c: c.execute(
                "SELECT tracking_round FROM tasks WHERE task_id=?", (identifier,)
            ).fetchone()[0],
            write=False,
        )
        assert rounds == 2
        stale = await call(
            a,
            "abandon_task",
            task_id=identifier,
            expected_version=abandoned["version"],
            reason="new decision",
            acknowledge_remote_may_continue=True,
        )
        assert stale["error"] == "VERSION_CONFLICT"
        assert stale["task"]["version"] == results[0]["version"]


async def test_copy_cancellation_before_publish_preserves_target(surface, tmp_path, monkeypatch):
    facade, adapter, http = surface
    async with protocol() as a, protocol() as b:
        task = await submit(a)
        identifier = task["task_id"]
        await facade.scheduler.dispatch()
        adapter.status = "completed"
        await facade.scheduler.refresh(identifier)
        artifact = (await facade.artifacts.register(identifier, [{"url": http.url + "/video"}]))[0]
        http.responses.append((200, {}, video()))
        await facade.artifacts.download(artifact)
        entered = threading.Event()
        release = threading.Event()
        cancelled = asyncio.Event()
        original = facade.artifacts.copy

        def hook(point):
            if point == "copy_before_publish":
                entered.set()
                release.wait(5)

        async def copy(*args, **kwargs):
            try:
                return await original(*args, **kwargs, hook=hook)
            except asyncio.CancelledError:
                cancelled.set()
                raise

        monkeypatch.setattr(facade.artifacts, "copy", copy)
        target = tmp_path / "protected.mp4"
        target.write_bytes(b"existing user file")
        operation = asyncio.create_task(
            call(a, "copy_artifact", artifact_id=artifact, target_path=str(target), overwrite=True)
        )
        assert await asyncio.to_thread(entered.wait, 5)
        operation.cancel()
        with pytest.raises(asyncio.CancelledError):
            await operation
        await asyncio.sleep(0.15)
        release.set()
        await asyncio.wait_for(cancelled.wait(), 5)
        assert target.read_bytes() == b"existing user file"
        assert (await call(b, "get_task", task_id=identifier))["delivery"] == "ready"


async def test_bounded_pages_and_oversized_response_preserve_identity(surface, monkeypatch):
    facade, _, _ = surface
    from dataclasses import replace

    limits = dict(facade.config.limits) | {"TOOL_RESPONSE_BYTES_LIMIT": 3000}
    facade.config = replace(facade.config, limits=limits)
    facade.queries.config = facade.config
    async with protocol() as session:
        for i in range(5):
            await submit(session, str(i))
        page = await call(session, "list_tasks", limit=5)
        assert 0 < len(page["items"]) < 5
        assert len(json.dumps(page, ensure_ascii=False).encode()) < 3000
        assert page["next_cursor"]
        task = page["items"][0]

        async def oversized(task_id):
            return task | {"untrusted_extra": "x" * 40000}

        monkeypatch.setattr(facade.queries, "get", oversized)
        result = await call(session, "get_task", task_id=task["task_id"])
        assert result["truncated"] and result["task_id"] == task["task_id"]
        assert result["version"] == task["version"] and result["allowed_actions"]
        assert "untrusted_extra" not in result


async def test_observed_progress_changes_version_but_observation_time_does_not(surface):
    from dataclasses import replace

    facade, adapter, _ = surface
    async with protocol() as session:
        task = await submit(session)
        identifier = task["task_id"]
        await facade.scheduler.dispatch()
        await facade.scheduler.refresh(identifier)
        first = await call(session, "get_task", task_id=identifier)
        await facade.scheduler.refresh(identifier)
        same = await call(
            session,
            "wait_task",
            task_id=identifier,
            after_version=first["version"],
            timeout_seconds=0.01,
        )
        assert same["wait_timed_out"]
        row = await facade.scheduler._row(identifier)
        observation = replace(await adapter.query(row), progress=75)
        await facade.state.observe(
            identifier, observation, operation_epoch=row["epoch"], now="later"
        )
        changed = await call(
            session,
            "wait_task",
            task_id=identifier,
            after_version=first["version"],
            timeout_seconds=0,
        )
        assert not changed["wait_timed_out"] and changed["progress"] == 75
