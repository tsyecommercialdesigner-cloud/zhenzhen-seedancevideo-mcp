import json
from dataclasses import replace

import httpx2
import pytest
from test_artifacts import video

from zhenzhen_seedance_video import runtime
from zhenzhen_seedance_video.config import (
    ConfigurationConflict,
    ConfigurationError,
    accept_explicit_configuration,
    load_configuration,
)
from zhenzhen_seedance_video.lifecycle import Lifecycle
from zhenzhen_seedance_video.models import BASE_URL
from zhenzhen_seedance_video.network import NetworkError, NetworkPolicy, origin
from zhenzhen_seedance_video.production import CODE, ProductionAdapter, quarantine_unapproved
from zhenzhen_seedance_video.provider import ProviderFailure
from zhenzhen_seedance_video.storage import Database, StorageError


@pytest.fixture
def harness(monkeypatch):
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_API_KEY", "synthetic-entry")
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_EXECUTION_MODE", "provider")
    calls = []

    async def respond(request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/v1/files/upload":
            return httpx2.Response(
                200,
                json={
                    "url": "https://media.example/input.mp4",
                    "size": len(video()),
                    "file_type": "video",
                    "expires_in": 3600,
                },
            )
        if request.method == "POST":
            payload = json.loads(request.content)
            assert payload["model"] == "zhenzhen-upscaler"
            assert (
                payload["metadata"]["content"][0]["video_url"]["url"]
                == "https://media.example/input.mp4"
            )
            assert "enhance_prompt" not in payload
            return httpx2.Response(
                200,
                json={
                    "id": "task_synthetic",
                    "object": "video",
                    "status": "queued",
                    "model": "zhenzhen-upscaler",
                },
            )
        if request.url.path.startswith("/v1/"):
            return httpx2.Response(
                200,
                json={
                    "id": "task_synthetic",
                    "object": "video",
                    "model": "zhenzhen-upscaler",
                    "status": "completed",
                    "metadata": {"url": "https://media.example/output.mp4"},
                },
            )
        return httpx2.Response(200, content=video())

    def network(config):
        return NetworkPolicy(
            config,
            _test_origins=[origin(BASE_URL), origin("https://media.example")],
            _transport=httpx2.MockTransport(respond),
        )

    async def run(scenario):
        monkeypatch.setattr(Lifecycle, "run", scenario)
        await runtime.run_backend(network_factory=network)
        # The test runs consecutive backends inside one pytest process; its PID stays alive.
        # The backend has closed ownership before removing this test-only discovery record.
        (load_configuration().root / "runtime/discovery.json").unlink()

    return run, calls


async def test_default_provider_composition_upload_delivery_and_restart(harness, tmp_path):
    run, calls = harness
    source = tmp_path / "source.mp4"
    source.write_bytes(video())
    payload = {
        "model": "zhenzhen-upscaler",
        "metadata": {
            "resolution": "720p",
            "content": [{"type": "video_url", "video_url": {"url": {"local_path": str(source)}}}],
        },
    }
    task = {}

    async def first(life):
        assert isinstance(life.scheduler.adapter, ProductionAdapter)
        accepted = await life.admission.submit("entry", payload, api_id="zhenzhen-upscaler")
        task.update(accepted)
        assert await life.scheduler.dispatch() == []  # No Host, no upload or POST.
        assert calls == []
        life.leases.join("host-a")
        await life.scheduler.dispatch()
        row = await life.scheduler._row(task["task_id"])
        assert row["remote_id"] == "task_synthetic", (row["attention"], calls)

    await run(first)

    async def second(life):
        life.leases.join("host-b")
        replay = await life.admission.submit("entry", payload, api_id="zhenzhen-upscaler")
        assert replay["task_id"] == task["task_id"]
        await life.scheduler.refresh(task["task_id"])
        await life.scheduler.deliver_due()
        for work in list(life.artifacts.work.values()):
            await work
        item = (await life.artifacts.list(task["task_id"]))["items"][0]
        assert item["state"] == "ready"
        await life.artifacts.copy(item["artifact_id"], str(tmp_path / "delivered.mp4"))
        assert (tmp_path / "delivered.mp4").read_bytes() == source.read_bytes()
        assert (await life.scheduler._row(task["task_id"]))["delivery"] == "partial"

    await run(second)
    assert calls.count(("POST", "/v1/video/generations")) == 1
    assert calls.count(("POST", "/v1/files/upload")) == 1


@pytest.mark.parametrize("legacy", [False, True])
async def test_local_and_legacy_tasks_never_gain_permission(harness, monkeypatch, legacy):
    run, calls = harness
    task = {}
    payload = {"model": "seedance-2.0-mini-t2v", "prompt": "synthetic", "enhance_prompt": False}
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_EXECUTION_MODE", "local")

    async def local(life):
        assert life.scheduler is None
        task.update(await life.admission.submit("old", payload))
        with pytest.raises(NetworkError, match="PROVIDER_EXECUTION_DISABLED"):
            await life.artifacts.network.request("GET", BASE_URL, phase="query")
        with pytest.raises(NetworkError, match="PROVIDER_EXECUTION_DISABLED"):
            async with life.artifacts.network.stream("GET", BASE_URL, phase="download"):
                pytest.fail("local stream opened")
        if legacy:

            def remove(c):
                r = c.execute("SELECT details FROM task_events WHERE kind='accepted'").fetchone()
                details = json.loads(r[0])
                details.pop("provider_execution_authorized")
                c.execute(
                    "UPDATE task_events SET details=? WHERE kind='accepted'", (json.dumps(details),)
                )

            await life.db.execute(remove)

    await run(local)
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_EXECUTION_MODE", "provider")

    async def provider(life):
        life.leases.join("host")
        replay = await life.admission.submit("old", payload)
        assert replay["task_id"] == task["task_id"]
        row = await life.scheduler._row(task["task_id"])
        assert row["auto_mode"] == "needs_attention" and CODE in row["attention"]
        assert await life.scheduler.dispatch() == []
        for operation in (
            life.scheduler.adapter.prepare,
            life.scheduler.adapter.query,
            life.scheduler.adapter.artifacts,
            life.scheduler.uploads.prepare,
        ):
            with pytest.raises(ProviderFailure, match=CODE):
                await operation(row)
        with pytest.raises(ProviderFailure, match=CODE):
            await life.scheduler.adapter.submit(row, payload)

    await run(provider)
    await run(provider)
    assert calls == []


def test_mode_priority_conflicts_and_invalid(monkeypatch, tmp_path):
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_API_KEY", "synthetic")
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_EXECUTION_MODE", "provider")
    from zhenzhen_seedance_video.config import installation_root

    path = installation_root() / ".env"
    path.write_text("ZHENZHEN_SEEDANCE_EXECUTION_MODE=local\n")
    config = load_configuration()
    assert config.execution_mode == "local"
    assert accept_explicit_configuration(config, config.root, {}).execution_mode == "local"
    with pytest.raises(ConfigurationConflict):
        accept_explicit_configuration(config, config.root, {"EXECUTION_MODE": "provider"})
    path.write_text("ZHENZHEN_SEEDANCE_EXECUTION_MODE=true\n")
    with pytest.raises(ConfigurationError):
        load_configuration()


async def test_quarantine_failure_rolls_back(monkeypatch, harness):
    run, _ = harness

    async def seed(life):
        # Simulate an old admission without enabling network work.
        life.admission.config = replace(life.config, execution_mode="local")
        await life.admission.submit("old", {"model": "seedance-2.0-mini-t2v", "prompt": "test"})

    await run(seed)
    db = Database(load_configuration().state_dir)
    try:
        await db.execute(
            lambda c: c.execute(
                "CREATE TRIGGER deny_guard BEFORE UPDATE ON tasks "
                "BEGIN SELECT RAISE(ABORT, 'synthetic'); END"
            )
        )
        with pytest.raises(StorageError):
            await quarantine_unapproved(db)
        row = await db.execute(
            lambda c: c.execute("SELECT auto_mode FROM tasks").fetchone(), write=False
        )
        assert row[0] == "active"
    finally:
        await db.close()
