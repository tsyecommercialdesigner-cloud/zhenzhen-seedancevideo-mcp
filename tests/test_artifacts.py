import asyncio
import json
import struct
import threading
from pathlib import Path

import pytest

from zhenzhen_seedance_video.artifact_files import (
    ArtifactError,
    copy_async,
    destination,
    fingerprint,
)
from zhenzhen_seedance_video.artifacts import ArtifactService
from zhenzhen_seedance_video.config import load_configuration
from zhenzhen_seedance_video.network import NetworkPolicy, origin
from zhenzhen_seedance_video.storage import Database
from zhenzhen_seedance_video.task_state import TaskState


def video(brand=b"isom"):
    def box(kind, payload):
        return struct.pack(">I4s", len(payload) + 8, kind) + payload

    return (
        box(b"ftyp", brand + b"\0" * 4) + box(b"moov", b"synthetic") + box(b"mdat", b"fake-video")
    )


@pytest.fixture
async def delivery(monkeypatch, tmp_path, fake_http, clock):
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_API_KEY", "synthetic")
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_DOWNLOAD_RETRIES", "1")
    config = load_configuration()
    db = Database(config.state_dir)
    await db.execute(
        lambda c: c.execute(
            "INSERT INTO tasks(task_id,request_key,api_id,model,kind,rule_version,intent_digest,"
            "effective_parameters,output_dir,connection_binding,created_at,"
            "remote_state,remote_id,stage,delivery) "
            "VALUES "
            "('task','key','seedance-video','synthetic','t2v','1','hash','{}',?,'binding','now',"
            "'succeeded','remote','downloading','pending')",
            (str(tmp_path / "outputs"),),
        )
    )
    policy = NetworkPolicy(config, _test_origins=[origin(fake_http.url)])
    service = ArtifactService(db, config, policy, wall=lambda: clock.utc)
    try:
        yield service, fake_http, clock
    finally:
        await service.close()
        await policy.close()
        await service.db.close()


async def register(service, http, **kwargs):
    return (await service.register("task", [{"url": http.url + "/video", **kwargs}]))[0]


async def ready(service, http):
    identifier = await register(service, http)
    http.responses.append((200, {}, video()))
    await service.download(identifier)
    return identifier


async def test_success_download_list_copy_no_generation_or_billing(delivery, tmp_path):
    service, http, _ = delivery
    identifier = await ready(service, http)
    item = (await service.list("task"))["items"][0]
    assert item["state"] == "ready"
    assert "source_url" not in item
    assert "url" not in json.dumps(item)
    assert await asyncio.to_thread(Path(item["target_path"]).read_bytes) == video()
    state = await TaskState(service.db).get("task")
    assert state["delivery"] == "ready" and state["cleanup_state"] == "pending"
    assert all(method == "GET" for method, _, _ in http.requests)
    result = await service.copy(
        identifier, "nested/result.mp4", workspace_root=str(tmp_path / "workspace")
    )
    assert await asyncio.to_thread(Path(result["path"]).read_bytes) == video()
    with pytest.raises(ArtifactError, match="TARGET_EXISTS"):
        await service.copy(identifier, result["path"])
    assert not (await service.copy(identifier, item["target_path"]))["copied"]
    assert (await service.copy(identifier, result["path"], overwrite=True))["copied"]


@pytest.mark.parametrize("payload", [b"", b"<html>error</html>", video()[:-1], video(b"qt  ")])
async def test_bad_container_or_length_no_ready(delivery, payload):
    service, http, _ = delivery
    identifier = await register(service, http)
    http.responses.append((200, {}, payload))
    await service.download(identifier)
    assert (await service.list("task"))["items"][0]["state"] == "attention"
    assert (await TaskState(service.db).get("task"))["cleanup_state"] == "none"


async def test_mov_preserves_container(delivery):
    service, http, _ = delivery
    identifier = await register(service, http, format="mov")
    http.responses.append((200, {}, video(b"qt  ")))
    await service.download(identifier)
    assert (await service.verify(identifier))["state"] == "ready"


async def test_finite_retry_and_restart_does_not_reset_budget(delivery):
    service, http, clock = delivery
    identifier = await register(service, http)
    http.responses.extend([(503, {}, b"fail"), (503, {}, b"fail")])
    await service.download(identifier)
    await service.download(identifier)
    assert len(http.requests) == 1
    await service.recover()
    clock.advance(70)
    await service.download(identifier)
    assert (await service.verify(identifier))["state"] == "attention"
    await service.recover()
    await service.due()
    assert len(http.requests) == 2
    state = await TaskState(service.db).get("task")
    await service.retry("task", expected_version=state["version"])
    http.responses.append((200, {}, video()))
    await service.download(identifier)
    assert (await service.verify(identifier))["state"] == "ready"


@pytest.mark.parametrize("point", ["download_before_publish", "download_after_publish"])
async def test_publish_crash_recovers_with_file_identity(delivery, point):
    service, http, _ = delivery
    identifier = await register(service, http)
    http.responses.append((200, {}, video()))

    def crash(current):
        if current == point:
            raise RuntimeError("synthetic-crash")

    service.hook = crash
    with pytest.raises(RuntimeError, match="synthetic-crash"):
        await service.download(identifier)
    service.hook = lambda _: None
    await service.recover()
    if point == "download_before_publish":
        http.responses.append((200, {}, video()))
        await service.download(identifier)
    assert (await service.verify(identifier))["state"] == "ready"


async def test_unrelated_same_content_target_not_adopted(delivery):
    service, http, _ = delivery
    identifier = await register(service, http)
    http.responses.append((200, {}, video()))

    def crash(point):
        if point == "download_before_publish":
            raise RuntimeError("crash")

    service.hook = crash
    with pytest.raises(RuntimeError):
        await service.download(identifier)
    artifact, _ = await service._get(identifier)
    await asyncio.to_thread(Path(artifact["target_path"]).write_bytes, video())
    await service.recover()
    assert (await service.verify(identifier))["state"] == "attention"
    assert await asyncio.to_thread(Path(artifact["target_path"]).read_bytes) == video()


async def test_multi_partial_and_expired_link(delivery):
    service, http, _ = delivery
    ids = await service.register("task", [{"url": http.url + "/a"}, {"url": http.url + "/b"}])
    http.responses.extend([(200, {}, video()), (403, {}, b"private")])
    for identifier in ids:
        await service.download(identifier)
    state = await TaskState(service.db).get("task")
    assert state["delivery"] == "partial" and state["cleanup_state"] == "none"
    assert "ARTIFACT_LINK_REFRESH_UNVERIFIED" in state["attention"]
    page = await service.list("task", limit=1)
    assert page["next_cursor"]
    assert len((await service.list("task", after=page["next_cursor"]))["items"]) == 1


async def test_external_change_no_automatic_download_explicit_overwrite(delivery):
    service, http, _ = delivery
    identifier = await ready(service, http)
    item = await service.verify(identifier)
    path = Path(item["target_path"])
    await asyncio.to_thread(path.write_bytes, b"user-edit")
    assert (await service.verify(identifier))["state"] == "changed"
    await service.due()
    assert len(http.requests) == 1
    state = await TaskState(service.db).get("task")
    with pytest.raises(ArtifactError, match="TARGET_EXISTS"):
        await service.retry("task", expected_version=state["version"])
    await service.retry("task", expected_version=state["version"], overwrite=True)
    assert await asyncio.to_thread(path.read_bytes) == b"user-edit"
    http.responses.append((200, {}, video()))
    await service.download(identifier)
    assert await asyncio.to_thread(path.read_bytes) == video()
    await asyncio.to_thread(path.unlink)
    assert (await service.verify(identifier))["state"] == "missing"


@pytest.mark.parametrize(
    "value", [r"\\server\share\file", "C:relative", r"C:\foo:stream", "NUL", "x."]
)
def test_reject_unsafe_paths(value, tmp_path):
    with pytest.raises((ArtifactError, RuntimeError)):
        destination(value, str(tmp_path))


def test_relative_escape_and_no_workspace(tmp_path):
    with pytest.raises(ArtifactError, match="OUTSIDE"):
        destination("../outside", str(tmp_path))
    with pytest.raises(ArtifactError, match="WORKSPACE_REQUIRED"):
        destination("file")


async def test_copy_race_cancel_and_response_loss(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(video())
    proof = fingerprint(source)
    target = tmp_path / "target.mp4"

    def race(point):
        if point == "copy_before_publish":
            target.write_bytes(b"other")

    with pytest.raises(ArtifactError):
        await copy_async(source, target, proof, hook=race)
    assert target.read_bytes() == b"other"
    entered, release = threading.Event(), threading.Event()

    def pause(point):
        if point == "copy_before_publish":
            entered.set()
            release.wait(3)

    work = asyncio.create_task(copy_async(source, target, proof, overwrite=True, hook=pause))
    assert await asyncio.to_thread(entered.wait, 3)
    work.cancel()
    await asyncio.sleep(0)
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await work
    assert target.read_bytes() == b"other"

    def lost(point):
        if point == "copy_after_publish":
            raise RuntimeError("response-lost")

    with pytest.raises(RuntimeError, match="response-lost"):
        await copy_async(source, target, proof, overwrite=True, hook=lost)
    assert target.read_bytes() == video() and source.read_bytes() == video()
    assert not list(tmp_path.glob(".seedance-copy-*"))


async def test_parent_rename_locked_and_symlink_rejected(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(video())
    parent = tmp_path / "parent"
    parent.mkdir()

    def attack(point):
        if point == "copy_before_publish":
            with pytest.raises(OSError):
                parent.rename(tmp_path / "renamed")

    await copy_async(source, parent / "out.mp4", fingerprint(source), hook=attack)
    link = tmp_path / "link"
    try:
        link.symlink_to(parent, target_is_directory=True)
        with pytest.raises(RuntimeError, match="UNSAFE"):
            destination(str(link / "out.mp4"))
    finally:
        if link.is_symlink():
            link.unlink()


async def test_download_concurrency_limit_and_interrupted_stream(delivery):
    from contextlib import asynccontextmanager

    from zhenzhen_seedance_video.network import NetworkError

    service, http, _ = delivery
    ids = await service.register("task", [{"url": http.url + f"/{n}"} for n in range(4)])
    active, maximum = 0, 0
    both_started = asyncio.Event()

    class Response:
        status_code = 200
        headers = {}

        async def aiter_bytes(self):
            yield video()[:8]
            await asyncio.wait_for(both_started.wait(), 3)
            raise NetworkError("SYNTHETIC_DISCONNECT")

    class Network:
        @asynccontextmanager
        async def stream(self, *args, **kwargs):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            if active == 2:
                both_started.set()
            try:
                yield Response()
            finally:
                active -= 1

    service.network = Network()
    await service.due()
    assert maximum == service.config.limits["DOWNLOAD_CONCURRENCY"]
    for identifier in ids:
        artifact, _ = await service._get(identifier)
        assert artifact["state"] == "pending" and artifact["temporary_path"] is None


async def test_length_mismatch_and_disk_failure(delivery, monkeypatch):
    from contextlib import asynccontextmanager

    service, http, _ = delivery
    identifier = await register(service, http)

    class Response:
        status_code = 200
        headers = {"content-length": "999"}

        async def aiter_bytes(self):
            yield video()

    class Network:
        @asynccontextmanager
        async def stream(self, *args, **kwargs):
            yield Response()

    service.network = Network()
    await service.download(identifier)
    assert "ARTIFACT_LENGTH_MISMATCH" in (await TaskState(service.db).get("task"))["attention"]
    state = await TaskState(service.db).get("task")
    await service.retry("task", expected_version=state["version"])
    original = Path.open

    def disk_full(path, *args, **kwargs):
        if ".download-" in path.name:
            raise OSError("synthetic disk full")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", disk_full)
    await service.download(identifier)
    assert "ARTIFACT_STORAGE_ERROR" in (await TaskState(service.db).get("task"))["attention"]


async def test_download_bytes_limit(delivery):
    from dataclasses import replace

    service, http, _ = delivery
    service.config = replace(
        service.config, limits=dict(service.config.limits) | {"DOWNLOAD_BYTES_LIMIT": 8}
    )
    identifier = await register(service, http)
    http.responses.append((200, {}, video()))
    await service.download(identifier)
    assert "ARTIFACT_BYTES_LIMIT" in (await TaskState(service.db).get("task"))["attention"]


async def test_database_reopen_after_publish_ready_write_failure(delivery):
    service, http, _ = delivery
    identifier = await register(service, http)
    http.responses.append((200, {}, video()))
    original = service._ready

    async def failed(*args):
        raise __import__("zhenzhen_seedance_video.storage", fromlist=["StorageError"]).StorageError(
            "STORAGE_FAULT"
        )

    service._ready = failed
    with pytest.raises(RuntimeError, match="STORAGE_FAULT"):
        await service.download(identifier)
    await service.db.close()
    service.db = Database(service.config.state_dir)
    service._ready = original
    await service.recover()
    assert (await service.verify(identifier))["state"] == "ready"
    assert len(http.requests) == 1


async def test_abandon_during_download_does_not_publish(delivery):
    from contextlib import asynccontextmanager

    service, http, _ = delivery
    identifier = await register(service, http)

    class Response:
        status_code = 200
        headers = {}

        async def aiter_bytes(self):
            yield video()
            state = await TaskState(service.db).get("task")
            await TaskState(service.db).abandon(
                "task", expected_version=state["version"], reason="stop", confirmed=True, now="now"
            )

    class Network:
        @asynccontextmanager
        async def stream(self, *args, **kwargs):
            yield Response()

    service.network = Network()
    await service.download(identifier)
    assert (await TaskState(service.db).get("task"))["auto_mode"] == "abandoned"
    assert (await service.verify(identifier))["state"] != "ready"


async def test_synthetic_scheduler_delivers_without_regeneration(delivery):
    from types import SimpleNamespace

    from zhenzhen_seedance_video.scheduler import Scheduler

    service, http, clock = delivery

    class Adapter:
        async def artifacts(self, row):
            assert row["remote_id"] == "remote"
            return [{"url": http.url + "/video"}]

    leases = SimpleNamespace(network_allowed=False, dispatch_allowed=False)
    scheduler = Scheduler(
        service.db,
        service.config,
        "binding",
        Adapter(),
        leases=leases,
        delivery=service,
        wall=lambda: clock.utc,
        monotonic=lambda: clock.monotonic,
    )
    try:
        await scheduler.deliver_due()
        assert not http.requests
        leases.network_allowed = True
        http.responses.append((200, {}, video()))
        await scheduler.deliver_due()
        await scheduler.deliver_due()
        assert len(http.requests) == 1
        assert (await TaskState(service.db).get("task"))["delivery"] == "ready"
    finally:
        await scheduler.close()


async def test_same_size_edit_detected_by_digest_and_copy_preserves_target(delivery, tmp_path):
    service, http, _ = delivery
    identifier = await ready(service, http)
    item = await service.verify(identifier)
    path = Path(item["target_path"])
    await asyncio.to_thread(path.write_bytes, b"x" * len(video()))
    assert (await service.list("task"))["items"][0]["state"] == "ready"
    assert (await service.verify(identifier))["state"] == "changed"
    target = tmp_path / "keep.mp4"
    await asyncio.to_thread(target.write_bytes, b"keep")
    with pytest.raises(ArtifactError, match="ARTIFACT_NOT_READY"):
        await service.copy(identifier, str(target), overwrite=True)
    assert await asyncio.to_thread(target.read_bytes) == b"keep"


def jpeg():
    # Structural-only synthetic JPEG, not a decodable photograph.
    return bytes.fromhex("ffd8 ffc0000b080001000101011100 ffda0008010100003f00 01 ffd9")


async def test_jpeg_tail_download_copy_partial_and_recovery(delivery, tmp_path):
    service, http, _ = delivery
    identifiers = await service.register(
        "task",
        [
            {"url": http.url + "/video.mp4", "format": "mp4"},
            {"url": http.url + "/tail.png", "format": "jpg"},
        ],
        complete=False,
    )
    http.responses.extend([(200, {}, video()), (200, {"Content-Type": "image/jpeg"}, jpeg())])
    for identifier in identifiers:
        await service.download(identifier)
    items = (await service.list("task"))["items"]
    assert all(item["state"] == "ready" for item in items)
    assert (await TaskState(service.db).get("task"))["delivery"] == "partial"
    assert (await TaskState(service.db).get("task"))["cleanup_state"] == "none"
    await service.recover()
    result = await service.copy(identifiers[1], "tail.jpg", workspace_root=str(tmp_path))
    assert await asyncio.to_thread(Path(result["path"]).read_bytes) == jpeg()
    assert result["path"].endswith(".jpg")


@pytest.mark.parametrize("payload", [b"\xff\xd8\xff\xd9", jpeg()[:-1], b"\x89PNG\r\n\x1a\n"])
async def test_invalid_or_unverified_tail_encoding_rejected(delivery, payload):
    service, http, _ = delivery
    identifier = await register(service, http, format="jpg")
    http.responses.append((200, {}, payload))
    await service.download(identifier)
    assert (await service.list("task"))["items"][0]["state"] == "attention"
