import asyncio
import json
import threading
from dataclasses import replace

import pytest

from zhenzhen_seedance_video.admission import AdmissionError, AdmissionService
from zhenzhen_seedance_video.config import load_configuration
from zhenzhen_seedance_video.materials import MaterialError, locked_source, receive
from zhenzhen_seedance_video.storage import Database, StorageError


@pytest.fixture
async def intake(monkeypatch):
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_API_KEY", "synthetic")
    config = load_configuration()
    db = Database(config.state_dir)
    service = AdmissionService(db, config, "test-binding")
    try:
        yield service
    finally:
        await service.close()
        await service.db.close()


def request(source=None):
    value = {"model": "seedance-2.0-mini-t2v", "prompt": "fox", "seconds": "5"}
    if source:
        value.update(model="seedance-2.0-mini-i2v", images=[{"local_path": str(source)}])
    return value


@pytest.mark.asyncio
async def test_concurrent_copies_dedup_and_readonly_find(intake, tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(b"original")
    results = await asyncio.gather(*(intake.submit("same", request(source)) for _ in range(12)))
    assert len({r["task_id"] for r in results}) == 1
    assert len(list(intake.root.iterdir())) == 1
    assert all(r["accepted"] for r in results)
    source.unlink()
    assert (await intake.find("same"))["task_id"] == results[0]["task_id"]
    assert next(intake.root.iterdir()).read_bytes() == b"original"


@pytest.mark.asyncio
async def test_same_path_changed_and_independent_key(intake, tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(b"first")
    first = await intake.submit("a", request(source))
    source.write_bytes(b"other")
    with pytest.raises(AdmissionError, match="REQUEST_KEY_CONFLICT"):
        await intake.submit("a", request(source))
    second = await intake.submit("b", request(source))
    assert first["task_id"] != second["task_id"]
    assert len(list(intake.root.iterdir())) == 2


@pytest.mark.asyncio
async def test_capacity_and_failed_intake_releases_reservation(intake, tmp_path):
    intake.config = replace(
        intake.config,
        limits=dict(intake.config.limits) | {"QUEUE_LIMIT": 1, "INPUT_BYTES_LIMIT": 3},
    )
    source = tmp_path / "source.png"
    source.write_bytes(b"oversize")
    with pytest.raises(MaterialError, match="INPUT_BYTES_LIMIT"):
        await intake.submit("a", request(source))
    assert (await intake.find("a"))["status"] == "not_found"
    assert not list(intake.root.iterdir())
    accepted = await intake.submit("a", request())
    assert (await intake.submit("a", request())) == accepted
    with pytest.raises(AdmissionError, match="QUEUE_FULL"):
        await intake.submit("b", request())


@pytest.mark.asyncio
async def test_url_signature_and_upscale_independent_copy(intake, tmp_path):
    url = "https://cdn.example/source.mp4?X-Signature=Secret%2Fvalue&expires=12"
    payload = {
        "model": "zhenzhen-upscaler",
        "metadata": {"content": [{"type": "video_url", "video_url": {"url": url}}]},
    }
    await intake.submit("url", payload, api_id="zhenzhen-upscaler")
    stored = await intake.db.execute(
        lambda c: c.execute("SELECT effective_parameters FROM tasks").fetchone()[0], write=False
    )
    assert json.loads(stored)["metadata"]["content"][0]["video_url"]["url"] == url
    assert not list(intake.root.iterdir())
    source = tmp_path / "output.mp4"
    source.write_bytes(b"original-video")
    payload["metadata"]["content"][0]["video_url"]["url"] = {"local_path": str(source)}
    await intake.submit("upscale", payload, api_id="zhenzhen-upscaler")
    assert source.read_bytes() == b"original-video"
    assert next(intake.root.iterdir()).read_bytes() == source.read_bytes()


@pytest.mark.asyncio
async def test_authorization_priority_revoke_and_restart(intake):
    first = await intake.submit("default", request())
    assert first["authorization"]["enabled"] is False
    with pytest.raises(AdmissionError, match="AUTHORIZATION_REQUIRED"):
        await intake.submit("forbidden", request() | {"enhance_prompt": True})
    one = await intake.submit("once", request(), allow_once=True)
    assert one["authorization"]["source"] == "single_allow"
    assert (await intake.get_preference())["enabled"] is False
    policy = await intake.set_preference(enabled=True, expected_version=0, confirmed=True)
    assert policy == {"enabled": True, "version": 1}
    second_client = AdmissionService(intake.db, intake.config, "test-binding")
    assert (await second_client.get_preference()) == policy
    allowed = await intake.submit("always", request())
    assert allowed["authorization"]["source"] == "always_allow"
    off = await intake.submit("off", request() | {"enhance_prompt": False})
    assert not off["authorization"]["enabled"]
    await second_client.set_preference(enabled=False, expected_version=1, confirmed=True)
    assert (await intake.submit("always", request())) == allowed
    with pytest.raises(AdmissionError, match="CONFLICT"):
        await intake.submit("always", request() | {"enhance_prompt": False})
    await intake.close()
    await intake.db.close()
    intake.db = Database(intake.config.state_dir)
    assert await intake.get_preference() == {"enabled": False, "version": 2}
    assert (await intake.find("always")) == allowed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model,metadata,api",
    [
        ("seedance-2.5-standard-draft-to-video", {"draft_task_id": "task_draft"}, "seedance-video"),
        (
            "zhenzhen-upscaler",
            {"content": [{"type": "video_url", "video_url": {"url": "https://cdn.example/x.mp4"}}]},
            "zhenzhen-upscaler",
        ),
    ],
)
async def test_authorization_not_applicable(intake, model, metadata, api):
    await intake.set_preference(enabled=True, expected_version=0, confirmed=True)
    accepted = await intake.submit("a", {"model": model, "metadata": metadata}, api_id=api)
    assert accepted["authorization"]["source"] == "not_applicable"
    stored = await intake.db.execute(
        lambda c: c.execute("SELECT effective_parameters FROM tasks").fetchone()[0], write=False
    )
    assert "enhance_prompt" not in json.loads(stored)


@pytest.mark.asyncio
async def test_cancel_wait_does_not_cancel_reception_and_revoke_during_copy(
    intake, tmp_path, monkeypatch
):
    import zhenzhen_seedance_video.admission as module

    original = module.receive
    started, release = threading.Event(), threading.Event()

    def slow(*args, **kwargs):
        started.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "receive", slow)
    source = tmp_path / "source.png"
    source.write_bytes(b"input")
    await intake.set_preference(enabled=True, expected_version=0, confirmed=True)
    waiting = asyncio.create_task(intake.submit("a", request(source)))
    assert await asyncio.to_thread(started.wait, 5)
    assert (await intake.find("a"))["status"] == "receiving"
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting
    await intake.set_preference(enabled=False, expected_version=1, confirmed=True)
    release.set()
    await asyncio.gather(*list(intake._inflight.values()))
    found = await intake.find("a")
    assert found["accepted"] and found["authorization"]["enabled"] is False


@pytest.mark.asyncio
async def test_crash_reservation_recovery_preserves_accepted(intake):
    accepted = await intake.submit("a", request())
    name = "a" * 32 + ".input"
    (intake.root / name).write_bytes(b"partial")
    await intake.db.execute(
        lambda c: (
            c.execute(
                "INSERT INTO admissions VALUES (?,?,?,?,?,?)",
                ("orphan", "op", "digest", 5, json.dumps([name]), "now"),
            ).rowcount
        )
    )
    await intake.recover()
    assert not (intake.root / name).exists()
    assert (await intake.find("orphan"))["status"] == "not_found"
    assert await intake.find("a") == accepted


@pytest.mark.asyncio
async def test_fault_blocks_preference_and_new_file_effect(intake, tmp_path):
    intake.db._fault.set()
    with pytest.raises(StorageError):
        await intake.set_preference(enabled=True, expected_version=0, confirmed=True)
    assert not (await intake.get_preference())["enabled"]
    with pytest.raises(StorageError):
        await intake.submit("a", request())
    assert not list(intake.root.iterdir())


def test_source_lock_prevents_mutation(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"original")
    with locked_source(str(source)):
        with pytest.raises(OSError):
            source.write_bytes(b"changed")
    assert receive(str(source), limit=100)["size_bytes"] == 8


def test_changed_identity_fails_and_removes_partial(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import zhenzhen_seedance_video.materials as module

    original = module.os.fstat
    calls = 0

    def changed(fd):
        nonlocal calls
        result = original(fd)
        calls += 1
        if calls == 2:
            return SimpleNamespace(
                st_dev=result.st_dev,
                st_ino=result.st_ino,
                st_size=result.st_size + 1,
                st_mtime_ns=result.st_mtime_ns,
            )
        return result

    monkeypatch.setattr(module.os, "fstat", changed)
    source, target = tmp_path / "source", tmp_path / "copy"
    source.write_bytes(b"input")
    with pytest.raises(MaterialError, match="MATERIAL_CHANGED"):
        receive(str(source), limit=100, destination=target)
    assert not target.exists() and source.exists()


@pytest.mark.asyncio
async def test_same_digest_repair_only_before_submission(intake, tmp_path):
    from zhenzhen_seedance_video.task_state import StateError, TaskState

    source = tmp_path / "input.png"
    source.write_bytes(b"original")
    accepted = await intake.submit("repair", request(source))
    mid = accepted["materials"][0]["material_id"]
    managed = intake.root / (mid + ".input")
    managed.unlink()
    source.write_bytes(b"differnt")
    with pytest.raises(AdmissionError, match="MATERIAL_CONTENT_CONFLICT"):
        await intake.repair(accepted["task_id"], mid, str(source), expected_version=1)
    state = TaskState(intake.db)
    kwargs = dict(
        expected_version=1, connection_binding="test-binding", limit=3, now="now", deadline="later"
    )
    with pytest.raises(StateError, match="MATERIAL_NOT_READY"):
        await state.begin_submission(accepted["task_id"], **kwargs)
    source.write_bytes(b"original")
    repaired = await intake.repair(accepted["task_id"], mid, str(source), expected_version=1)
    assert repaired["version"] == 2 and managed.read_bytes() == b"original"
    submitted = await state.begin_submission(
        accepted["task_id"], **(kwargs | {"expected_version": 2})
    )
    with pytest.raises(AdmissionError, match="MATERIAL_REPAIR_NOT_ALLOWED"):
        await intake.repair(
            accepted["task_id"], mid, str(source), expected_version=submitted["version"]
        )


@pytest.mark.asyncio
async def test_old_defaults_and_same_effective_parameters(intake, monkeypatch):
    import zhenzhen_seedance_video.admission as module

    original = module.normalize
    accepted = await intake.submit("defaults", request())
    explicit = request() | {"enhance_prompt": False, "metadata": {"generate_audio": True}}
    assert await intake.submit("defaults", explicit) == accepted

    def changed_defaults(*args, **kwargs):
        raise AssertionError("Original explicit replay must not reapply defaults")

    monkeypatch.setattr(module, "normalize", changed_defaults)
    assert await intake.submit("defaults", request()) == accepted
    monkeypatch.setattr(module, "normalize", original)


@pytest.mark.asyncio
async def test_commit_failure_never_acknowledges_and_retains_for_recovery(
    intake, tmp_path, monkeypatch
):
    source = tmp_path / "input.png"
    source.write_bytes(b"input")
    original = intake.db.execute

    async def fail(function, **kwargs):
        if function.__name__ == "accept":
            intake.db._fault.set()
            raise StorageError("STORAGE_FAULT")
        return await original(function, **kwargs)

    monkeypatch.setattr(intake.db, "execute", fail)
    with pytest.raises(StorageError):
        await intake.submit("a", request(source))
    assert (await intake.find("a"))["status"] == "receiving"
    assert len(list(intake.root.iterdir())) == 1
    monkeypatch.setattr(intake.db, "execute", original)
    intake.db._fault.clear()  # Test-only simulation of a successful offline storage reconciliation.
    await intake.recover()
    assert (await intake.find("a"))["status"] == "not_found"
    assert not list(intake.root.iterdir())


@pytest.mark.asyncio
async def test_stale_reservation_does_not_delete_committed_material(intake, tmp_path):
    source = tmp_path / "input.png"
    source.write_bytes(b"input")
    accepted = await intake.submit("a", request(source))
    name = accepted["materials"][0]["material_id"] + ".input"
    await intake.db.execute(
        lambda c: (
            c.execute(
                "INSERT INTO admissions VALUES (?,?,?,?,?,?)",
                ("a", "stale", "digest", 5, json.dumps([name]), "now"),
            ).rowcount
        )
    )
    await intake.recover()
    assert (intake.root / name).read_bytes() == b"input"
    assert await intake.find("a") == accepted


@pytest.mark.asyncio
async def test_media_identity_does_not_rewrite_prompt_or_external_url(intake, tmp_path):
    source = tmp_path / "input.png"
    source.write_bytes(b"input")
    url = "https://managed.invalid/input/0"
    payload = {
        "model": "seedance-2.0-mini-multi",
        "prompt": url,
        "metadata": {
            "content": [
                {"type": "image_url", "image_url": {"url": {"local_path": str(source)}}},
                {"type": "video_url", "video_url": {"url": url}},
            ]
        },
    }
    await intake.submit("collision", payload)
    stored = await intake.db.execute(
        lambda c: c.execute("SELECT effective_parameters FROM tasks").fetchone()[0], write=False
    )
    result = json.loads(stored)
    assert result["prompt"] == url
    assert result["metadata"]["content"][1]["video_url"]["url"] == url
    assert isinstance(result["metadata"]["content"][0]["image_url"]["url"], dict)


@pytest.mark.asyncio
async def test_missing_source_retry_same_key(intake, tmp_path):
    source = tmp_path / "missing.png"
    with pytest.raises(MaterialError, match="MATERIAL_UNAVAILABLE_OR_BUSY"):
        await intake.submit("missing", request(source))
    assert (await intake.find("missing"))["status"] == "not_found"
    source.write_bytes(b"now present")
    assert (await intake.submit("missing", request(source)))["accepted"]
