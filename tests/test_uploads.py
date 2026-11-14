import hashlib
import io
import json
from pathlib import Path

import httpx2
import pytest

from zhenzhen_seedance_video.config import load_configuration
from zhenzhen_seedance_video.models import BASE_URL
from zhenzhen_seedance_video.network import NetworkError, NetworkPolicy, origin
from zhenzhen_seedance_video.provider import ProviderFailure
from zhenzhen_seedance_video.uploads import UploadError, decode_upload, upload_once


@pytest.fixture
def response():
    documented = json.loads(
        (Path(__file__).parent / "fixtures/provider/documented/upload-success.json").read_bytes()
    )
    # Documentation has a non-usable placeholder URL; this replacement is synthetic.
    documented["url"] = "https://cdn.example.com/input.png?signature=private"
    return documented


def decode(data):
    return decode_upload(json.dumps(data).encode(), expected_size=3490, expected_type="image")


def test_documented_shape_and_unknown_expiry(response):
    ref = decode(response)
    assert ref.size == 3490 and ref.expires_in == 86400
    assert "signature" not in repr(ref) and "private" not in repr(ref)
    del response["expires_in"]
    assert decode(response).expires_in is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("expires_in", True),
        ("expires_in", -1),
        ("expires_in", "86400"),
        ("size", True),
        ("size", 4),
        ("file_type", "video"),
        ("url", "https://.../input.png"),
        ("url", "https://user:pass@example.com/x"),
        ("url", "http://example.com/x"),
        ("url", "https://127.0.0.1/x"),
        ("url", "https://example.com/x#private"),
    ],
)
def test_invalid_metadata_is_not_accepted(response, field, value):
    response[field] = value
    with pytest.raises(UploadError) as error:
        decode(response)
    assert "private" not in str(error.value)


@pytest.mark.parametrize("body", [b'{"size":1,"size":2}', b'{"x":NaN}', b"[]", b"{"])
def test_invalid_envelopes(body):
    with pytest.raises(UploadError):
        decode_upload(body, expected_size=1, expected_type="image")


async def run_upload(policy, stream, **overrides):
    args = dict(
        suffix=".png",
        expected_size=3,
        expected_sha256=hashlib.sha256(b"abc").hexdigest(),
        byte_limit=10,
    )
    args.update(overrides)
    return await upload_once(policy, stream, **args)


async def test_multipart_bytes_auth_and_no_local_name(response, tmp_path):
    requests = []
    response["size"] = 3

    async def respond(request):
        requests.append(request)
        body = await request.aread()
        assert b'name="file"; filename="material.png"' in body
        assert b"Content-Type: image/png" in body and b"abc" in body
        assert request.headers["authorization"] == "Bearer synthetic"
        assert request.url.path == "/v1/files/upload"
        return httpx2.Response(200, json=response)

    config = load_configuration(
        environ={"ZHENZHEN_SEEDANCE_API_KEY": "synthetic", "LOCALAPPDATA": str(tmp_path)}
    )
    policy = NetworkPolicy(
        config, _test_origins=[origin(BASE_URL)], _transport=httpx2.MockTransport(respond)
    )
    stream = io.BytesIO(b"abc")
    try:
        assert (await run_upload(policy, stream)).size == 3
        assert len(requests) == 1 and not stream.closed
    finally:
        await policy.close()


@pytest.mark.parametrize("status", [401, 429, 500, 302])
async def test_failed_upload_never_retries_or_generates(status, tmp_path):
    seen = []

    async def respond(request):
        seen.append(request.url.path)
        return httpx2.Response(
            status, headers={"location": "https://other.example/x"}, content=b"private error"
        )

    config = load_configuration(
        environ={"ZHENZHEN_SEEDANCE_API_KEY": "synthetic", "LOCALAPPDATA": str(tmp_path)}
    )
    policy = NetworkPolicy(
        config, _test_origins=[origin(BASE_URL)], _transport=httpx2.MockTransport(respond)
    )
    try:
        with pytest.raises((ProviderFailure, NetworkError)) as error:
            await run_upload(policy, io.BytesIO(b"abc"))
        assert "private" not in str(error.value)
        assert seen == ["/v1/files/upload"]
    finally:
        await policy.close()


async def test_changed_material_stops_before_network():
    with pytest.raises(UploadError, match="MATERIAL_CHANGED"):
        await run_upload(None, io.BytesIO(b"abd"))
    with pytest.raises(UploadError, match="INPUT_LIMIT"):
        await run_upload(None, io.BytesIO(b"abc"), byte_limit=2)


def test_response_limit():
    with pytest.raises(UploadError, match="RESPONSE_LIMIT"):
        decode_upload(b" " * 65537, expected_size=1, expected_type="image")
