import json
from pathlib import Path
from types import SimpleNamespace

import httpx2
import pytest

from zhenzhen_seedance_video.admission import AdmissionService
from zhenzhen_seedance_video.compatibility_adapter import CompatibilityAdapter
from zhenzhen_seedance_video.config import load_configuration
from zhenzhen_seedance_video.models import BASE_URL
from zhenzhen_seedance_video.network import NetworkPolicy, origin
from zhenzhen_seedance_video.provider import ProviderFailure
from zhenzhen_seedance_video.provider_response import ResponseError
from zhenzhen_seedance_video.scheduler import Scheduler
from zhenzhen_seedance_video.storage import Database

FIXTURES = Path(__file__).parent / "fixtures/provider/user-supplied"


def sample(name):
    return (FIXTURES / name).read_bytes()


@pytest.fixture
async def setup(monkeypatch, clock, request):
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_API_KEY", "synthetic-key")
    config = load_configuration()
    responses, requests = [], []

    async def respond(request):
        requests.append(request)
        outcome = responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        status, content = outcome
        return httpx2.Response(status, content=content)

    network = NetworkPolicy(
        config, _test_origins=[origin(BASE_URL)], _transport=httpx2.MockTransport(respond)
    )
    adapter = CompatibilityAdapter(network)
    db = Database(config.state_dir)
    admission = AdmissionService(db, config, "binding")
    payload = getattr(request, "param", None) or {
        "model": "seedance-2.0-mini-t2v",
        "prompt": "fox",
        "enhance_prompt": False,
    }
    payload = dict(payload)
    allow_once = payload.pop("_test_allow_once", False)
    accepted = await admission.submit(
        "request",
        payload,
        allow_once=allow_once,
        api_id="zhenzhen-upscaler" if payload["model"] == "zhenzhen-upscaler" else "seedance-video",
    )
    scheduler = Scheduler(
        db,
        config,
        "binding",
        adapter,
        leases=SimpleNamespace(dispatch_allowed=True, network_allowed=True),
        wall=lambda: clock.utc,
        monotonic=lambda: clock.monotonic,
    )
    try:
        yield scheduler, adapter, responses, requests, accepted["task_id"], clock
    finally:
        await scheduler.close()
        await admission.close()
        await db.close()
        await network.close()


async def test_submit_progress_success_persisted_without_billing(setup):
    engine, adapter, responses, requests, tid, _ = setup
    responses.extend(
        (200, sample(name))
        for name in ("submit-queued.json", "query-in-progress.json", "query-completed.json")
    )
    before = await engine._row(tid)
    assert await engine.dispatch() == [tid]
    assert (await engine._row(tid))["remote_state"] == "queued"
    assert (await engine.refresh(tid))["remote_state"] == "running"
    assert (await engine.refresh(tid))["remote_state"] == "succeeded"
    after = await engine._row(tid)
    assert after["delivery"] == "pending" and not after["generation_slot_held"]
    assert after["charge_state"] == "not_returned" and after["actual_amount"] is None
    assert json.loads(requests[0].content) == json.loads(before["effective_parameters"])
    assert json.loads(requests[0].content)["enhance_prompt"] is False
    assert [r.method for r in requests] == ["POST", "GET", "GET"]
    assert requests[0].url.path == "/v1/video/generations"
    assert all(r.url.path == "/v1/video/generations/task_xxxxxxxxxxxx" for r in requests[1:])
    assert all(r.headers["authorization"] == "Bearer synthetic-key" for r in requests)
    facts = await engine.db.execute(
        lambda c: json.loads(
            c.execute(
                "SELECT facts FROM remote_observations ORDER BY rowid DESC LIMIT 1"
            ).fetchone()[0]
        ),
        write=False,
    )
    assert facts["url"] == json.loads(sample("query-completed.json"))["metadata"]["url"]


async def test_failed_sample_and_no_retry(setup):
    engine, _, responses, requests, tid, _ = setup
    responses.extend([(200, sample("submit-queued.json")), (200, sample("query-failed.json"))])
    await engine.dispatch()
    state = await engine.refresh(tid)
    assert state["remote_state"] == "failed" and state["stage"] == "settled"
    assert await engine.dispatch() == []
    assert len(requests) == 2


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500])
async def test_http_error_does_not_prove_unsubmitted(setup, status):
    engine, _, responses, requests, tid, _ = setup
    responses.append((status, b'{"message":"private-signature"}'))
    await engine.dispatch()
    row = await engine._row(tid)
    assert row["remote_state"] == "unknown" and row["generation_slot_held"]
    assert row["auto_mode"] == "needs_attention"
    await engine.dispatch()
    assert len(requests) == 1 and "private" not in row["attention"]


async def test_submit_timeout_no_retry_query_timeout_uses_budget(setup):
    engine, _, responses, requests, tid, _ = setup
    responses.append(httpx2.ReadTimeout("private signed URL"))
    await engine.dispatch()
    await engine.dispatch()
    assert len(requests) == 1 and (await engine._row(tid))["remote_state"] == "unknown"


@pytest.mark.parametrize("change", ["wrong_id", "SUCCESS", "malformed", "missing_url"])
async def test_unverified_response_branches(setup, change):
    engine, _, responses, requests, tid, _ = setup
    responses.append((200, sample("submit-queued.json")))
    await engine.dispatch()
    value = json.loads(sample("query-completed.json"))
    if change == "wrong_id":
        value["id"] = "other"
    elif change == "SUCCESS":
        value = {"data": {"status": "SUCCESS", "usage": {"amount": 8.75, "currency": "CNY"}}}
    elif change == "missing_url":
        value["metadata"] = {}
    responses.append((200, b"invalid" if change == "malformed" else json.dumps(value).encode()))
    result = await engine.query(tid, explicit=False)
    row = await engine._row(tid)
    assert len(requests) == 2 and row["remote_id"] == "task_xxxxxxxxxxxx"
    if change == "missing_url":
        assert row["remote_state"] == "succeeded" and not row["generation_slot_held"]
        assert "RESULT_URL_UNAVAILABLE" in row["attention"]
    else:
        assert result["query_succeeded"] is False and row["remote_state"] == "queued"
        assert row["generation_slot_held"]
    assert row["auto_mode"] == "needs_attention" and row["actual_amount"] is None


async def test_query_transport_failure_is_temporary_without_submit_replay(setup):
    engine, _, responses, requests, tid, _ = setup
    responses.extend([(200, sample("submit-queued.json")), httpx2.ReadTimeout("private")])
    await engine.dispatch()
    row = await engine._row(tid)
    before = await engine._budget(row)
    await engine.query(tid, explicit=False)
    after = await engine._budget(await engine._row(tid))
    assert after["remaining_budget"] == before["remaining_budget"] - 1
    assert (await engine._row(tid))["auto_mode"] == "active"
    assert [r.method for r in requests] == ["POST", "GET"]


@pytest.mark.parametrize("identifier", ["..", "x/y", "x?key=secret", "x#fragment", ""])
async def test_remote_id_cannot_change_route(setup, identifier):
    engine, adapter, _, requests, tid, _ = setup
    row = (await engine._row(tid)) | {"remote_id": identifier}
    with pytest.raises(ProviderFailure, match="REMOTE_ID_PATH_UNVERIFIED"):
        await adapter.query(row)
    assert not requests


async def test_prepare_rejects_unresolved_material_and_keeps_policy_snapshot(setup):
    engine, adapter, _, requests, tid, _ = setup
    row = await engine._row(tid)
    payload = json.loads(row["effective_parameters"])
    payload["images"] = [{"material_id": "unresolved"}]
    with pytest.raises(ProviderFailure, match="MATERIAL_PREPARATION_REQUIRED"):
        await adapter.prepare(row | {"effective_parameters": json.dumps(payload)})
    assert not requests
    assert (await adapter.prepare(row))["enhance_prompt"] is False


async def test_success_envelope_is_explicitly_rejected(setup):
    engine, adapter, responses, _, tid, _ = setup
    responses.append((200, b'{"data":{"status":"SUCCESS"}}'))
    row = (await engine._row(tid)) | {"remote_id": "task_xxxxxxxxxxxx"}
    with pytest.raises(ResponseError, match="SUCCESS_ENVELOPE_UNVERIFIED"):
        await adapter.query(row)


async def test_artifact_set_gate_does_not_crash_scheduler(setup):
    engine, _, responses, _, tid, _ = setup
    responses.extend([(200, sample("submit-queued.json")), (200, sample("query-completed.json"))])
    await engine.dispatch()
    await engine.refresh(tid)

    class Delivery:
        async def register(self, *args):
            pytest.fail("unverified artifact set must not be registered")

        async def due(self):
            pass

        async def close(self):
            pass

    engine.delivery = Delivery()
    await engine.deliver_due()
    row = await engine._row(tid)
    assert row["remote_state"] == "succeeded" and row["auto_mode"] == "needs_attention"
    assert "ARTIFACT_SET_UNVERIFIED" in row["attention"]


async def test_failure_error_code_is_persisted_without_raw_message(setup):
    from zhenzhen_seedance_video.queries import Queries

    engine, _, responses, _, tid, _ = setup
    value = json.loads(sample("query-failed.json"))
    value["error"]["message"] = "Traceback private signed URL and secret"
    responses.extend([(200, sample("submit-queued.json")), (200, json.dumps(value).encode())])
    await engine.dispatch()
    await engine.refresh(tid)
    snapshot = await Queries(engine.db, engine.config).get(tid)
    assert snapshot["remote_error_code"] == "video_generation_failed"
    assert "private" not in json.dumps(snapshot) and "Traceback" not in json.dumps(snapshot)
    observations = await engine.db.execute(
        lambda c: [r[0] for r in c.execute("SELECT facts FROM remote_observations")], write=False
    )
    assert "private" not in str(observations)


async def test_contradictory_terminal_observation_and_unverified_charge(setup):
    engine, _, responses, _, tid, _ = setup
    completed = json.loads(sample("query-completed.json"))
    # Synthetic extra billing fragment is not contract evidence and must not become a charge.
    completed["data"] = {"usage": {"amount": 8.75, "currency": "CNY"}}
    responses.extend(
        [
            (200, sample("submit-queued.json")),
            (200, json.dumps(completed).encode()),
            (200, sample("query-failed.json")),
        ]
    )
    await engine.dispatch()
    await engine.refresh(tid)
    await engine.refresh(tid)
    row = await engine._row(tid)
    assert row["remote_state"] == "succeeded" and row["actual_amount"] is None
    assert "REMOTE_TERMINAL_CONFLICT" in row["attention"]


async def test_query_redirect_cannot_switch_compatibility_endpoint(setup):
    engine, adapter, _, requests, tid, _ = setup
    seen = []

    async def redirect(request):
        seen.append(request.url.path)
        return httpx2.Response(302, headers={"location": BASE_URL + "/v1/videos/task_xxxxxxxxxxxx"})

    network = NetworkPolicy(
        engine.config, _test_origins=[origin(BASE_URL)], _transport=httpx2.MockTransport(redirect)
    )
    try:
        guarded = CompatibilityAdapter(network)
        with pytest.raises(ProviderFailure, match="QUERY_NETWORK_FAILED"):
            await guarded.query((await engine._row(tid)) | {"remote_id": "task_xxxxxxxxxxxx"})
        assert seen == ["/v1/video/generations/task_xxxxxxxxxxxx"]
        assert not requests
    finally:
        await network.close()


async def test_live_fixture_query_charge_manifest_and_reopen(setup):
    engine, adapter, responses, requests, tid, clock = setup
    live = FIXTURES.parent / "live-observed"
    bodies = [
        (live / f"{name}.json").read_bytes()
        for name in ("submit-queued", "query-in-progress", "query-success-usage")
    ]
    responses.extend((200, body) for body in bodies)
    await engine.dispatch()
    assert (await engine.refresh(tid))["remote_state"] == "running"
    await engine.refresh(tid)
    row = await engine._row(tid)
    assert row["remote_id"] == "task_live_probe_01"
    assert row["actual_amount"] == "0.8028" and row["actual_currency"] == "¥"
    assert row["charge_state"] == "confirmed" and row["delivery"] == "pending"
    adapter.db = engine.db
    manifest = await adapter.artifacts(row)
    assert manifest.complete is False
    # Duplicate observation neither accumulates money nor advances the version.
    responses.append((200, bodies[-1]))
    await engine.refresh(tid)
    assert (await engine._row(tid))["version"] == row["version"]
    assert (
        await engine.db.execute(
            lambda c: c.execute("SELECT COUNT(*) FROM charge_observations").fetchone()[0],
            write=False,
        )
        == 1
    )
    # Missing later fees cannot erase the confirmed charge or use nested token usage.
    missing = json.loads(bodies[-1])
    del missing["data"]["usage"]
    responses.append((200, json.dumps(missing).encode()))
    await engine.refresh(tid)
    assert (await engine._row(tid))["actual_amount"] == "0.8028"
    assert len(requests) == 5 and all("/v1/videos" not in r.url.path for r in requests)
    state_dir = engine.config.state_dir
    await engine.db.close()
    reopened = Database(state_dir)
    try:
        saved = await reopened.execute(
            lambda c: dict(c.execute("SELECT * FROM tasks WHERE task_id=?", (tid,)).fetchone()),
            write=False,
        )
        assert saved["actual_currency"] == "¥" and saved["actual_amount"] == "0.8028"
        adapter.db = reopened
        assert (await adapter.artifacts(saved)).complete is False
    finally:
        await reopened.close()


async def test_live_charge_storage_failure_rolls_back_terminal_observation(setup, monkeypatch):
    import sqlite3

    from zhenzhen_seedance_video import charges
    from zhenzhen_seedance_video.provider_response import decode_response
    from zhenzhen_seedance_video.storage import StorageError
    from zhenzhen_seedance_video.task_state import TaskState

    engine, _, responses, _, tid, _ = setup
    live = FIXTURES.parent / "live-observed"
    responses.append((200, (live / "submit-queued.json").read_bytes()))
    await engine.dispatch()
    before = await engine._row(tid)
    observation = decode_response(
        (live / "query-success-usage.json").read_bytes(),
        expected_model=before["model"],
        expected_id=before["remote_id"],
    )
    original = charges.record_charge_transaction

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise sqlite3.OperationalError("synthetic transaction failure")

    monkeypatch.setattr(charges, "record_charge_transaction", fail)
    with pytest.raises(StorageError):
        await TaskState(engine.db).observe(
            tid, observation, operation_epoch=before["epoch"], now="later"
        )
    after = await engine._row(tid)
    assert after["remote_state"] == before["remote_state"]
    assert after["version"] == before["version"] and after["actual_amount"] is None
    assert (
        await engine.db.execute(
            lambda c: c.execute("SELECT COUNT(*) FROM charge_observations").fetchone()[0],
            write=False,
        )
        == 0
    )


async def test_live_success_conflict_does_not_record_charge(setup):
    engine, _, responses, _, tid, _ = setup
    live = FIXTURES.parent / "live-observed"
    submitted = (live / "submit-queued.json").read_bytes()
    failure = json.loads(sample("query-failed.json"))
    failure["id"] = "task_live_probe_01"
    responses.extend(
        [
            (200, submitted),
            (200, json.dumps(failure).encode()),
            (200, (live / "query-success-usage.json").read_bytes()),
        ]
    )
    await engine.dispatch()
    await engine.refresh(tid)
    await engine.refresh(tid)
    row = await engine._row(tid)
    assert row["remote_state"] == "failed" and row["actual_amount"] is None
    assert "REMOTE_TERMINAL_CONFLICT" in row["attention"]
    facts = await engine.db.execute(
        lambda c: json.loads(
            c.execute(
                "SELECT facts FROM remote_observations ORDER BY rowid DESC LIMIT 1"
            ).fetchone()[0]
        ),
        write=False,
    )
    assert facts["provider_status"] == "SUCCESS"


async def test_observed_last_frame_manifest_persisted(setup):
    engine, adapter, responses, _, tid, _ = setup
    fixtures = FIXTURES.parent / "last-frame-observed"
    responses.extend(
        (200, (fixtures / name).read_bytes())
        for name in ("submit-queued.json", "query-success-last-frame.json")
    )
    await engine.dispatch()
    await engine.refresh(tid)
    adapter.db = engine.db
    manifest = await adapter.artifacts(await engine._row(tid))
    assert not manifest.complete and len(manifest.references) == 2
    assert manifest.references[1] == {
        "url": "https://example.invalid/last-frame.png",
        "format": "jpg",
        "required": True,
    }


@pytest.mark.parametrize(
    "setup,kind,amount",
    [
        (
            {
                "model": "zhenzhen-upscaler",
                "metadata": {
                    "resolution": "720p",
                    "content": [
                        {
                            "type": "video_url",
                            "video_url": {"url": "https://example.invalid/material.mp4"},
                        }
                    ],
                },
            },
            "upscale",
            "0.875",
        ),
        (
            {
                "model": "seedance-2.5-standard-t2v",
                "prompt": "cube",
                "seconds": "4",
                "enhance_prompt": False,
                "metadata": {"draft": True, "resolution": "480p"},
            },
            "draft",
            "2.688892",
        ),
    ],
    indirect=["setup"],
)
async def test_observed_upscale_and_draft_queue_persistence(setup, kind, amount):
    from zhenzhen_seedance_video.queries import Queries

    engine, adapter, responses, requests, tid, _ = setup
    fixture_root = FIXTURES.parent / "contracts-observed"
    responses.extend(
        (200, (fixture_root / name).read_bytes())
        for name in (
            f"submit-{kind}-response.json",
            f"query-{kind}-1-response.json",
            f"query-{kind}-3-response.json",
        )
    )
    await engine.dispatch()
    await engine.refresh(tid)
    await engine.refresh(tid)
    query = Queries(engine.db, engine.config)
    result = await query.get(tid)
    assert result["charge"] == {"state": "confirmed", "amount": amount, "currency": "¥"}
    assert result.get("draft_task_id") == ("task_draft_probe_01" if kind == "draft" else None)
    assert result["remote_state"] == "succeeded"
    adapter.db = engine.db
    assert len((await adapter.artifacts(await engine._row(tid))).references) == 1
    assert len(requests) == 3 and requests[0].url.path == "/v1/video/generations"
    if kind == "upscale":
        assert "prompt" not in json.loads(requests[0].content)
    await engine.db.close()
    reopened = Database(engine.config.state_dir)
    try:
        restored = await Queries(reopened, engine.config).get(tid)
        assert restored["charge"] == result["charge"]
        assert restored["authorization"] == result["authorization"]
        assert restored.get("draft_task_id") == result.get("draft_task_id")
    finally:
        await reopened.close()


@pytest.mark.parametrize("name,status", [("no-auth", 401), ("missing-task", 400)])
async def test_observed_query_errors_do_not_fail_generation(setup, name, status):
    engine, _, responses, _, tid, _ = setup
    responses.append((200, sample("submit-queued.json")))
    await engine.dispatch()
    responses.append(
        (status, (FIXTURES.parent / "contracts-observed" / f"{name}-response.json").read_bytes())
    )
    await engine.refresh(tid)
    row = await engine._row(tid)
    assert row["remote_state"] == "queued" and row["generation_slot_held"]


@pytest.mark.parametrize(
    "setup",
    [
        {
            "model": "seedance-2.0-mini-i2v",
            "prompt": "scene",
            "images": ["https://example.invalid/input.jpg"],
        }
    ],
    indirect=True,
)
async def test_observed_not_start_retains_submission_and_budget(setup):
    engine, _, responses, requests, tid, _ = setup
    root = FIXTURES.parent / "generation-queue-observed"
    responses.extend(
        (200, (root / name).read_bytes())
        for name in ("regular-submit.json", "regular-not-start.json", "regular-not-start.json")
    )
    await engine.dispatch()
    before = await engine._row(tid)
    await engine.refresh(tid)
    await engine.refresh(tid)
    after = await engine._row(tid)
    assert after["remote_state"] == "queued" and after["generation_slot_held"]
    assert after["tracking_round"] == before["tracking_round"]
    assert after["charge_state"] == "not_returned"
    assert sum(r.method == "POST" for r in requests) == 1
    facts = await engine.db.execute(
        lambda c: c.execute(
            "SELECT facts FROM remote_observations WHERE task_id=? ORDER BY rowid DESC LIMIT 1",
            (tid,),
        ).fetchone()[0],
        write=False,
    )
    assert json.loads(facts)["provider_status"] == "NOT_START"


@pytest.mark.parametrize(
    "setup,case",
    [
        (
            {
                "model": "seedance-2.0-mini-i2v",
                "prompt": "scene",
                "images": ["https://example.invalid/input.jpg"],
                "seconds": "4",
                "metadata": {"resolution": "480p"},
            },
            "regular",
        ),
        (
            {
                "model": "seedance-2.5-standard-t2v",
                "prompt": "cube",
                "seconds": "4",
                "metadata": {"draft": True, "resolution": "480p"},
            },
            "draft",
        ),
        (
            {
                "model": "seedance-2.5-standard-draft-to-video",
                "metadata": {
                    "draft_task_id": "task_draft_queue_01",
                    "resolution": "native1080p",
                    "output_format": "mp4",
                    "return_last_frame": False,
                },
            },
            "final",
        ),
        (
            {
                "model": "seedance-2.5-global-standard-t2v",
                "prompt": "cube",
                "seconds": "4",
                "enhance_prompt": False,
                "metadata": {"draft": True, "resolution": "480p"},
            },
            "global-draft",
        ),
        (
            {
                "model": "seedance-2.5-global-standard-draft-to-video",
                "metadata": {
                    "draft_task_id": "task_draft_queue_01",
                    "resolution": "native1080p",
                    "output_format": "mp4",
                    "return_last_frame": False,
                },
            },
            "global-final",
        ),
        (
            {
                "model": "seedance-2.0-global-fast-i2v",
                "prompt": "scene",
                "images": ["https://example.invalid/input.jpg"],
                "seconds": "4",
                "enhance_prompt": False,
                "metadata": {"resolution": "480p", "generate_audio": False},
            },
            "fastmulti-fast",
        ),
        (
            {
                "model": "seedance-2.0-standard-multi",
                "prompt": "scene from @Video 1 with @Image 1",
                "seconds": "4",
                "enhance_prompt": False,
                "metadata": {
                    "resolution": "480p",
                    "generate_audio": False,
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": "https://example.invalid/input.jpg"},
                        },
                        {
                            "type": "video_url",
                            "video_url": {"url": "https://example.invalid/input.mp4"},
                        },
                    ],
                },
            },
            "fastmulti-multi",
        ),
        (
            {
                "model": "seedance-2.0-mini-t2v",
                "prompt": "cube",
                "seconds": "4",
                "enhance_prompt": True,
                "_test_allow_once": True,
                "metadata": {"resolution": "480p", "generate_audio": False},
            },
            "optimization-optimized",
        ),
    ],
    indirect=["setup"],
)
async def test_real_generation_queue_evidence_persisted(setup, case):
    from decimal import Decimal

    from zhenzhen_seedance_video.queries import Queries

    engine, adapter, responses, requests, tid, _ = setup
    root = FIXTURES.parent / "generation-queue-observed"
    if case.startswith("global-"):
        root = FIXTURES.parent / "global-queue-observed"
        case = case.removeprefix("global-")
    if case.startswith("fastmulti-"):
        root = FIXTURES.parent / "fast-multi-queue-observed"
        case = case.removeprefix("fastmulti-")
    if case.startswith("optimization-"):
        root = FIXTURES.parent / "optimization-queue-observed"
        case = case.removeprefix("optimization-")
    success = (root / f"{case}-success.json").read_bytes()
    responses.extend([(200, (root / f"{case}-submit.json").read_bytes()), (200, success)])
    await engine.dispatch()
    await engine.refresh(tid)
    result = await Queries(engine.db, engine.config).get(tid)
    usage = json.loads(success, parse_float=Decimal)["data"]["usage"]
    assert result["remote_state"] == "succeeded"
    assert result["charge"] == {
        "state": "confirmed",
        "amount": str(usage["amount"]),
        "currency": usage["currency"],
    }
    assert result.get("draft_task_id") == ("task_draft_queue_01" if case == "draft" else None)
    adapter.db = engine.db
    manifest = await adapter.artifacts(await engine._row(tid))
    assert len(manifest.references) == 1 and not manifest.complete
    assert sum(request.method == "POST" for request in requests) == 1
    if case in ("fast", "multi"):
        payload = json.loads(requests[0].content)
        assert payload["enhance_prompt"] is False
        assert payload["seconds"] == "4"
        assert payload["metadata"]["resolution"] == "480p"
        if case == "multi":
            assert [item["type"] for item in payload["metadata"]["content"]] == [
                "image_url",
                "video_url",
            ]
            assert "omni_reference_task_type" not in payload["metadata"]
    if case == "optimized":
        payload = json.loads(requests[0].content)
        assert payload["enhance_prompt"] is True
        assert result["authorization"]["source"] == "single_allow"
        assert (
            await engine.db.execute(
                lambda c: c.execute("SELECT count(*) FROM preferences").fetchone()[0],
                write=False,
            )
            == 0
        )
    if case == "final":
        payload = json.loads(requests[0].content)
        assert not {"prompt", "images", "seconds", "enhance_prompt"} & payload.keys()
        assert payload["metadata"]["draft_task_id"] == "task_draft_queue_01"
    await engine.db.close()
    reopened = Database(engine.config.state_dir)
    try:
        restored = await Queries(reopened, engine.config).get(tid)
        assert restored["charge"] == result["charge"]
        assert restored["authorization"] == result["authorization"]
        assert restored.get("draft_task_id") == result.get("draft_task_id")
    finally:
        await reopened.close()
