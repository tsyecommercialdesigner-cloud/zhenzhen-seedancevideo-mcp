import asyncio
import json
from pathlib import Path

import pytest
from test_artifacts import video
from test_cleanup import cleanup as cleanup
from test_cleanup import jobs, transition
from test_compatibility_adapter import sample
from test_compatibility_adapter import setup as setup

from zhenzhen_seedance_video.artifact_files import ArtifactError
from zhenzhen_seedance_video.artifacts import ArtifactService
from zhenzhen_seedance_video.network import NetworkPolicy, origin
from zhenzhen_seedance_video.provider import ProviderFailure
from zhenzhen_seedance_video.queries import Queries
from zhenzhen_seedance_video.storage import Database


async def connect_delivery(setup, *, url="https://cdn.example.com/output.mp4?signature=private"):
    engine, adapter, responses, requests, tid, clock = setup
    adapter.db = engine.db
    adapter.network._test_origins |= {origin("https://cdn.example.com")}
    engine.delivery = ArtifactService(
        engine.db, engine.config, adapter.network, wall=lambda: clock.utc
    )
    completed = json.loads(sample("query-completed.json"))
    completed["metadata"]["url"] = url  # Synthetic transport URL, not new supplier evidence.
    responses.extend([(200, sample("submit-queued.json")), (200, json.dumps(completed).encode())])
    await engine.dispatch()
    await engine.refresh(tid)
    return engine.delivery, completed


async def test_main_video_download_copy_and_unknown_collection(setup, tmp_path):
    engine, adapter, responses, requests, tid, _ = setup
    delivery, completed = await connect_delivery(setup)
    responses.append((200, video()))
    await engine.deliver_due()
    item = (await delivery.list(tid))["items"][0]
    assert item["state"] == "ready"
    assert await asyncio.to_thread(Path(item["target_path"]).read_bytes) == video()
    snapshot = await Queries(engine.db, engine.config).get(tid)
    assert snapshot["artifact_set_status"] == "unverified"
    assert snapshot["delivery"] == "partial" and snapshot["remote_state"] == "succeeded"
    assert snapshot["cleanup_state"] != "pending" and snapshot["stage"] != "settled"
    assert "ARTIFACT_SET_UNVERIFIED" in snapshot["attention"]
    assert snapshot["charge"]["state"] == "not_returned"
    copied = await delivery.copy(
        item["artifact_id"], "nested/video.mp4", workspace_root=str(tmp_path / "work")
    )
    assert copied["size_bytes"] == item["size_bytes"]
    assert await asyncio.to_thread(Path(copied["path"]).read_bytes) == video()
    with pytest.raises(ArtifactError):
        await delivery.copy(item["artifact_id"], copied["path"])
    assert await asyncio.to_thread(Path(item["target_path"]).exists)
    assert [r.method for r in requests] == ["POST", "GET", "GET"]
    assert "authorization" not in requests[-1].headers
    assert "private" not in json.dumps(item) and "signature" not in json.dumps(snapshot)
    # Re-query does not turn partial into pending/ready or stop the known download path.
    responses.append((200, json.dumps(completed).encode()))
    await engine.refresh(tid)
    await engine.deliver_due()
    assert len(requests) == 4
    assert (await engine._row(tid))["delivery"] == "partial"
    assert len((await delivery.list(tid))["items"]) == 1


async def test_download_failure_then_explicit_recovery_keeps_generation(setup):
    engine, _, responses, requests, tid, _ = setup
    delivery, _ = await connect_delivery(setup)
    responses.append((403, b"expired"))
    await engine.deliver_due()
    row = await engine._row(tid)
    assert row["remote_state"] == "succeeded" and not row["generation_slot_held"]
    assert "ARTIFACT_LINK_REFRESH_UNVERIFIED" in row["attention"]
    await delivery.retry(tid, expected_version=row["version"])
    responses.append((200, video()))
    await engine.deliver_due()
    assert (await delivery.list(tid))["items"][0]["state"] == "ready"
    assert (await engine._row(tid))["delivery"] == "partial"
    assert sum(r.method == "POST" for r in requests) == 1


async def test_unknown_manifest_survives_database_reopen(setup):
    engine, adapter, responses, requests, tid, clock = setup
    delivery, _ = await connect_delivery(setup)
    responses.append((200, video()))
    await engine.deliver_due()
    original = (await delivery.list(tid))["items"][0]
    await engine.close()
    await engine.db.close()
    reopened = Database(engine.config.state_dir)
    restored = ArtifactService(reopened, engine.config, adapter.network, wall=lambda: clock.utc)
    try:
        await restored.recover()
        await restored.due()
        snapshot = await Queries(reopened, engine.config).get(tid)
        assert snapshot["artifact_set_status"] == "unverified" and snapshot["delivery"] == "partial"
        assert (await restored.list(tid))["items"][0]["sha256"] == original["sha256"]
        assert len(requests) == 3
        assert not await reopened.execute(
            lambda c: c.execute("SELECT 1 FROM cleanup_jobs").fetchone(), write=False
        )
    finally:
        await restored.close()
        await reopened.close()


@pytest.mark.parametrize(
    "url,explicit,expected",
    [
        ("https://cdn.example.com/output.mov", None, "mov"),
        ("https://[invalid/output.mp4", None, None),
        ("https://cdn.example.com/opaque?file=.mov", "mp4", "mp4"),
        ("https://cdn.example.com/opaque?file=.mp4", None, None),
        ("https://cdn.example.com/output.mp4", "mov", None),
    ],
)
async def test_format_is_explicit_or_path_only(setup, url, explicit, expected):
    engine, adapter, _, _, tid, _ = setup
    await connect_delivery(setup, url=url)
    row = await engine._row(tid)
    payload = json.loads(row["effective_parameters"])
    if explicit:
        payload.setdefault("metadata", {})["output_format"] = explicit
    row["effective_parameters"] = json.dumps(payload)
    if expected:
        manifest = await adapter.artifacts(row)
        assert manifest.references[0]["format"] == expected and manifest.complete is False
    else:
        with pytest.raises(ProviderFailure, match="ARTIFACT_FORMAT|RESULT_URL_UNAVAILABLE"):
            await adapter.artifacts(row)


async def test_reference_must_match_persisted_remote_id(setup):
    engine, adapter, _, _, tid, _ = setup
    await connect_delivery(setup)
    row = (await engine._row(tid)) | {"remote_id": "unrelated"}
    with pytest.raises(ProviderFailure, match="RESULT_URL_UNAVAILABLE"):
        await adapter.artifacts(row)


async def test_partial_main_retains_material_until_explicit_abandon(cleanup, fake_http):
    cleaner, _, tid, material, original, clock = cleanup
    policy = NetworkPolicy(cleaner.config, _test_origins=[origin(fake_http.url)])
    delivery = ArtifactService(cleaner.db, cleaner.config, policy, wall=lambda: clock.utc)
    try:
        await transition(
            cleaner, tid, remote_state="succeeded", stage="downloading", delivery="pending"
        )
        await delivery.register(
            tid,
            [{"url": fake_http.url + "/video.mp4", "format": "mp4", "required": True}],
            complete=False,
        )
        fake_http.responses.append((200, {}, video()))
        await delivery.due()
        await cleaner.scan()
        await cleaner.due()
        assert not await jobs(cleaner)
        assert await asyncio.to_thread(Path(material["managed_path"]).exists)
        await transition(cleaner, tid, auto_mode="abandoned")
        await cleaner.due()
        assert not await asyncio.to_thread(Path(material["managed_path"]).exists)
        assert await asyncio.to_thread(original.exists)
    finally:
        await delivery.close()
        await policy.close()
