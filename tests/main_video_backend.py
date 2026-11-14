"""Test-only real backend with compatibility parser and exclusively synthetic HTTP."""

import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path

import httpx2
from test_artifacts import video

from zhenzhen_seedance_video import cleanup as cleanup_module
from zhenzhen_seedance_video import runtime
from zhenzhen_seedance_video.artifacts import ArtifactService
from zhenzhen_seedance_video.compatibility_adapter import CompatibilityAdapter
from zhenzhen_seedance_video.models import BASE_URL
from zhenzhen_seedance_video.network import NetworkPolicy, origin
from zhenzhen_seedance_video.storage import Database
from zhenzhen_seedance_video.upload_service import UploadService

control, phase = Path(sys.argv[1]), sys.argv[3]
fixtures = Path(__file__).parent / "fixtures/provider/user-supplied"
material_mode = phase.startswith("material-")
multi_mode = phase.startswith("material-multi")
mixed_kinds = (
    [
        ("image", ".png", "image/png"),
        ("video", ".mp4", "video/mp4"),
        ("audio", ".mp3", "audio/mpeg"),
    ]
    if phase.endswith("mixed-video")
    else [
        ("video", ".mp4", "video/mp4"),
        ("audio", ".mp3", "audio/mpeg"),
        ("image", ".png", "image/png"),
    ]
    if phase.endswith("mixed-audio")
    else [("image", ".png", "image/png")] * 3
)
expiry_index = int(phase.split("-")[3]) if phase.startswith("material-multi-expiry-") else None


def material_url(index):
    renewed = expiry_index == index and (control / "crashed").exists()
    return upload_url + f"-{index}" + ("-renewed" if renewed else "")


input_bytes = b"synthetic-original-image"
upload_url = "https://cdn.example.com/input.png?signature=synthetic-input"

result_url = "https://cdn.example.com/output.mp4?signature=synthetic-private"


def record(kind):
    with (control / "requests.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"kind": kind}) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def sample(name):
    value = json.loads((fixtures / name).read_text(encoding="utf-8"))
    if material_mode:
        value["model"] = (
            "seedance-2.0-mini-multi" if multi_mode else "seedance-2.0-mini-i2v"
        )  # Synthetic model substitution.
    return value


async def respond(request):
    if request.url.host == "api.seedance.nz":
        assert request.headers["authorization"] == "Bearer synthetic"
        if request.url.path == "/v1/files/upload":
            assert request.method == "POST"
            assert request.headers["content-type"].startswith("multipart/form-data;")
            record("upload")
            attempts = sum(
                json.loads(line)["kind"] == "upload"
                for line in (control / "requests.jsonl").read_text().splitlines()
            )
            (control / "upload-entered").touch()
            while not (control / "release-upload").exists():  # noqa: ASYNC110 -- process gate
                await asyncio.sleep(0.02)
            body = await request.aread()
            if multi_mode:
                index = next(i for i in range(3) if f"synthetic-input-{i}".encode() in body)
                kind, suffix, mime = mixed_kinds[index]
                assert f'filename="material{suffix}"'.encode() in body
                assert f"Content-Type: {mime}\r\n".encode() in body
                assert b"private-" not in body
                record(f"material-{index}")
                seen = sum(
                    json.loads(line)["kind"] == f"material-{index}"
                    for line in (control / "requests.jsonl").read_text().splitlines()
                )
                if index == 1 and phase.startswith("material-multi-cleanup"):
                    (control / "second-inflight").touch()
                    while not (control / "release-second").exists():  # noqa: ASYNC110 -- process gate
                        await asyncio.sleep(0.02)
                if (
                    index == 1
                    and (
                        phase.startswith("material-multi-failure")
                        or phase.startswith("material-multi-exhaust")
                    )
                    and (seen == 1 or phase.startswith("material-multi-exhaust"))
                ):
                    return httpx2.Response(500, content=b"synthetic partial upload failure")
            else:
                assert input_bytes in body and b"changed-original" not in body
                assert b'filename="material.png"' in body
            if phase == "material-exhaust" or (phase == "material-retry" and attempts == 1):
                return httpx2.Response(500, content=b"synthetic failure")
            crash("material-upload")
            value = json.loads((fixtures.parent / "documented/upload-success.json").read_text())
            value.update(url=upload_url, size=len(input_bytes))
            if multi_mode:
                value.update(
                    url=material_url(index),
                    size=len(f"synthetic-input-{index}"),
                    file_type=kind,
                )
            if multi_mode and index == expiry_index and seen == 1:
                value["expires_in"] = 1
            if phase == "material-expiry" and attempts == 1:
                value["expires_in"] = 1
            return httpx2.Response(200, json=value)
        if request.method == "POST":
            assert request.url.path == "/v1/video/generations"
            if material_mode:
                payload = json.loads(request.content)
                if multi_mode:
                    assert payload["metadata"]["content"] == [
                        {"type": kind + "_url", kind + "_url": {"url": material_url(i)}}
                        for i, (kind, _, _) in enumerate(mixed_kinds)
                    ]
                else:
                    assert payload["images"] == [upload_url]
                assert "local_path" not in json.dumps(payload)
                assert "material_id" not in json.dumps(payload)
            record("submit")
            return httpx2.Response(200, json=sample("submit-queued.json"))
        assert request.method == "GET"
        assert request.url.path == "/v1/video/generations/task_xxxxxxxxxxxx"
        record("query")
        completed = (control / "complete").exists()
        value = sample("query-completed.json" if completed else "query-in-progress.json")
        if completed:
            value["metadata"]["url"] = result_url  # Explicit synthetic URL substitution.
        return httpx2.Response(200, json=value)
    assert str(request.url) == result_url and request.method == "GET"
    assert "authorization" not in request.headers
    record("download")
    if (control / "expired").exists():
        return httpx2.Response(403, content=b"synthetic expired")
    return httpx2.Response(200, content=video())


def crash(point):
    if phase == point and not (control / "crashed").exists():
        (control / "crashed").write_text(point)
        os._exit(91)


class Artifacts(ArtifactService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, hook=crash)


def network_factory(config):
    global network
    network = NetworkPolicy(
        config,
        _test_origins=[origin(BASE_URL), origin(result_url)],
        _transport=httpx2.MockTransport(respond),
    )
    return network


class Adapter(CompatibilityAdapter):
    async def prepare(self, row):
        payload = await super().prepare(row)
        crash("material-prepared")
        crash("material-expiry")
        if phase.startswith("material-multi-expiry"):
            crash(phase)
        return payload


class Uploads(UploadService):
    async def _one(self, *args, **kwargs):
        result = await super()._one(*args, **kwargs)
        if result is None:
            if phase.startswith("material-multi-failure"):
                crash(phase)
        return result


original_delete = cleanup_module.delete_copy


def synthetic_delete(root, material):
    index = material["ordinal"]
    record(f"delete-{index}")
    if phase.startswith("material-multi-cleanup-crash"):
        if index == 1 and "-zero-" in phase:
            attempts = sum(
                json.loads(line)["kind"] == "delete-1"
                for line in (control / "requests.jsonl").read_text().splitlines()
            )
            if attempts == 1:
                raise RuntimeError("CLEANUP_FILE_BUSY_OR_DENIED")
        if index == 1 and "crash-before" in phase:
            crash(phase)
        existed = Path(material["managed_path"]).exists()
        original_delete(root, material)
        if existed:
            record(f"removed-{index}")
        if index == 1 and "crash-after" in phase:
            crash(phase)
        return
    if index == 1 and not (control / "release-cleanup").exists():
        raise RuntimeError("CLEANUP_FILE_BUSY_OR_DENIED")
    return original_delete(root, material)


class Cleanup(cleanup_module.CleanupService):
    async def due(self):
        if "-concurrent-" in phase and (control / "pause-cleanup").exists():
            return
        await super().due()

    async def _failure(self, job, code):
        await super()._failure(job, code)
        if phase.startswith("material-multi-cleanup-retry"):
            crash(phase)


if phase.startswith(
    (
        "material-multi-cleanup-retry",
        "material-multi-cleanup-exhaust",
        "material-multi-cleanup-crash",
    )
):
    cleanup_module.delete_copy = synthetic_delete
    runtime.CleanupService = Cleanup


class FaultDatabase(Database):
    async def execute(self, function, *, write=True):
        if (
            write
            and function.__qualname__ == "CleanupService.scan.<locals>.collect"
            and (control / "fail-startup-scan").exists()
            and not (control / "startup-scan-injected").exists()
        ):

            def fail_scan(c):
                function(c)
                (control / "startup-scan-injected").touch()
                raise sqlite3.OperationalError("synthetic startup scan failure")

            return await super().execute(fail_scan, write=write)
        target = "intent" if "storage-intent" in phase else "complete"
        if (
            write is True
            and function.__qualname__ == f"CleanupService._perform.<locals>.{target}"
            and not (control / "storage-injected").exists()
        ):

            def inject(c):
                result = function(c)
                state = c.execute(
                    "SELECT j.state FROM cleanup_jobs j JOIN material_copies m USING(material_id) "
                    "WHERE m.ordinal=1"
                ).fetchone()
                if state and state[0] == ("deleting" if target == "intent" else "done"):
                    (control / "storage-injected").touch()
                    raise sqlite3.OperationalError("synthetic cleanup write failure")
                return result

            return await super().execute(inject, write=write)
        return await super().execute(function, write=write)


if phase.startswith("material-multi-cleanup-storage"):
    runtime.Database = FaultDatabase
    cleanup_module.delete_copy = synthetic_delete

original_rpc_start = runtime.RPCServer.start


async def recorded_rpc_start(self):
    if (control / "fail-startup-scan").exists():
        (control / "startup-rpc-started").touch()
    await original_rpc_start(self)


runtime.RPCServer.start = recorded_rpc_start
runtime.ArtifactService = Artifacts
asyncio.run(
    runtime.run_backend(
        adapter_factory=lambda db, config: Adapter(network, db),
        upload_factory=Uploads if material_mode else None,
        network_factory=network_factory,
    )
)
