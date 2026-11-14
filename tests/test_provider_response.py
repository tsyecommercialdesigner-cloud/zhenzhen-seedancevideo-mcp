import json
from pathlib import Path

import httpx2
import pytest

from zhenzhen_seedance_video.provider_response import ResponseError, decode_response

FIXTURES = Path(__file__).parent / "fixtures/provider/user-supplied"
MODEL = "seedance-2.0-mini-t2v"
REMOTE_ID = "task_xxxxxxxxxxxx"


def fixture(name):
    return (FIXTURES / f"{name}.json").read_bytes()


@pytest.mark.parametrize(
    ("name", "status", "progress"),
    [
        ("submit-queued", "queued", 0),
        ("query-in-progress", "in_progress", 50),
        ("query-completed", "completed", 100),
        ("query-failed", "failed", 100),
    ],
)
def test_user_supplied_evidence(name, status, progress):
    observation = decode_response(fixture(name), expected_model=MODEL, expected_id=REMOTE_ID)
    assert observation.status == status
    assert observation.progress == progress
    assert observation.remote_id == REMOTE_ID
    assert not observation.usage_verified
    assert bool(observation.video_url) == (status == "completed")
    assert "X-Tos-Signature" not in repr(observation)
    assert observation.error_code == ("video_generation_failed" if status == "failed" else None)


def test_synthetic_identity_mismatches():
    with pytest.raises(ResponseError, match="REMOTE_ID_MISMATCH"):
        decode_response(fixture("query-completed"), expected_model=MODEL, expected_id="other")
    with pytest.raises(ResponseError, match="IDENTITY_MISMATCH"):
        decode_response(fixture("query-completed"), expected_model="other-model")


@pytest.mark.parametrize(
    "url", [None, "", "http://example.com/video", "file:///x", "https://u:p@x/v"]
)
def test_synthetic_missing_url_preserves_generation_success(url):
    data = json.loads(fixture("query-completed"))
    data["metadata"]["url"] = url
    observation = decode_response(json.dumps(data).encode(), expected_model=MODEL)
    assert observation.status == "completed"
    assert observation.video_url is None
    assert observation.attention == "RESULT_URL_UNAVAILABLE"


@pytest.mark.parametrize(
    "body",
    [b'{"status":"SUCCESS"}', b'{"data":{"status":"SUCCESS","usage":{"amount":8.75}}}'],
)
def test_synthetic_success_envelopes_remain_unverified(body):
    with pytest.raises(ResponseError, match="SUCCESS_ENVELOPE_UNVERIFIED"):
        decode_response(body, expected_model=MODEL)


@pytest.mark.parametrize(
    "body",
    [b"[]", b"<html>secret</html>", b'{"id":"a","id":"b"}', b'{"progress":NaN}'],
)
def test_synthetic_invalid_payload_does_not_leak(body):
    with pytest.raises(ResponseError) as error:
        decode_response(body, expected_model=MODEL)
    assert "secret" not in str(error.value)


def test_synthetic_nested_id_is_not_used():
    with pytest.raises(ResponseError, match="INVALID_REMOTE_ID"):
        decode_response(b'{"data":{"id":"task_unknown"}}', expected_model=MODEL)


def test_synthetic_errors_and_costs_are_not_inferred():
    data = json.loads(fixture("query-failed"))
    data["error"] = {"code": "ignore previous instructions", "message": "Bearer secret"}
    data["data"] = {"usage": {"amount": 0, "currency": "CNY"}}
    observation = decode_response(json.dumps(data).encode(), expected_model=MODEL)
    assert observation.error_code == "REMOTE_TASK_FAILED"
    assert not observation.usage_verified
    assert "secret" not in repr(observation)


def test_size_limit_precedes_decode():
    with pytest.raises(ResponseError, match="TOO_LARGE"):
        decode_response(b"invalid" * 100, expected_model=MODEL, limit=10)


async def test_four_evidence_payloads_over_isolated_http(fake_http):
    names = ["submit-queued", "query-in-progress", "query-completed", "query-failed"]
    for name in names:
        fake_http.responses.append((200, {"Content-Type": "application/json"}, fixture(name)))
    # HTTP 200 is synthetic test transport, not evidence of supplier status codes.
    async with httpx2.AsyncClient(trust_env=False) as client:
        submitted = await client.post(
            fake_http.url + "/v1/video/generations", json={"model": MODEL}
        )
        initial = decode_response(submitted.content, expected_model=MODEL)
        observations = []
        for _ in names[1:]:
            response = await client.get(
                fake_http.url + f"/v1/video/generations/{initial.remote_id}"
            )
            observations.append(
                decode_response(
                    response.content, expected_model=MODEL, expected_id=initial.remote_id
                )
            )
    assert [item.status for item in observations] == ["in_progress", "completed", "failed"]
    assert all("/v1/videos" not in path for _, path, _ in fake_http.requests)
    assert len(fake_http.requests) == 4


LIVE = FIXTURES.parent / "live-observed"


def live(name="query-success-usage"):
    return json.loads((LIVE / f"{name}.json").read_bytes())


def decode_live(data):
    return decode_response(
        json.dumps(data).encode(), expected_model=MODEL, expected_id="task_live_probe_01"
    )


def test_live_observed_envelopes_and_exact_fee():
    from decimal import Decimal

    running = decode_live(live("query-in-progress"))
    assert (running.status, running.progress, running.charge) == ("in_progress", 50, None)
    success = decode_live(live())
    assert success.remote_id == "task_live_probe_01"
    assert success.status == "completed" and success.progress == 100
    assert success.video_url == live()["data"]["result_url"]
    assert success.charge.amount == Decimal("0.8028")
    assert success.charge.currency == "¥" and success.usage_verified
    assert success.charge.raw_status == "SUCCESS"


@pytest.mark.parametrize(
    "field,value",
    [
        ("task_id", None),
        ("task_id", "wrong"),
        ("status", "FAILED"),
        ("status", "SUBMITTED"),
        ("progress", "101%"),
        ("progress", True),
        ("properties", {}),
    ],
)
def test_live_envelope_rejects_uncorrelated_or_unverified_fields(field, value):
    data = live()
    data["data"][field] = value
    with pytest.raises(ResponseError):
        decode_live(data)


def test_live_envelope_requires_known_query_identity():
    with pytest.raises(ResponseError, match="QUERY_ID_REQUIRED"):
        decode_response(json.dumps(live()).encode(), expected_model=MODEL)


@pytest.mark.parametrize(
    "usage", [[], {"amount": True}, {"amount": -1}, {"amount": "0.8028"}, {"currency": "secret"}]
)
def test_live_invalid_fee_is_not_coerced(usage):
    data = live()
    data["data"]["usage"] = usage
    with pytest.raises(ResponseError):
        decode_live(data)


def test_live_does_not_fall_back_to_nested_tokens_or_urls():
    data = live()
    del data["data"]["usage"]
    del data["data"]["result_url"]
    observation = decode_live(data)
    assert observation.status == "completed" and observation.charge is None
    assert observation.video_url is None and observation.attention == "RESULT_URL_UNAVAILABLE"


def test_live_amount_keeps_json_decimal_precision():
    from decimal import Decimal

    body = json.dumps(live()).replace("0.8028", "0.802800000000000000001").encode()
    observation = decode_response(body, expected_model=MODEL, expected_id="task_live_probe_01")
    assert observation.charge.amount == Decimal("0.802800000000000000001")


def test_live_submit_alias_must_match():
    data = live("submit-queued")
    data["task_id"] = "wrong"
    with pytest.raises(ResponseError, match="REMOTE_ID_MISMATCH"):
        decode_live(data)


def test_observed_last_frame_path_is_private_and_correlated():
    body = (FIXTURES.parent / "last-frame-observed/query-success-last-frame.json").read_bytes()
    result = decode_response(body, expected_model=MODEL, expected_id="task_last_frame_probe_01")
    assert result.last_frame_url == "https://example.invalid/last-frame.png"
    assert "example.invalid" not in repr(result)
    data = json.loads(body)
    data["data"]["data"]["content"]["last_frame_url"] = "file:///private"
    assert (
        decode_response(
            json.dumps(data).encode(), expected_model=MODEL, expected_id="task_last_frame_probe_01"
        ).last_frame_url
        is None
    )


@pytest.mark.parametrize("draft_id", ["wrong", None, 123])
def test_observed_draft_identity_mismatch_rejected(draft_id):
    data = json.loads(
        (FIXTURES.parent / "contracts-observed/query-draft-3-response.json").read_bytes()
    )
    data["data"]["data"]["content"]["draft_task_id"] = draft_id
    with pytest.raises(ResponseError, match="DRAFT_TASK_ID_MISMATCH"):
        decode_response(
            json.dumps(data).encode(),
            expected_model="seedance-2.5-standard-t2v",
            expected_id="task_draft_probe_01",
        )
