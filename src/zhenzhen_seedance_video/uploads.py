"""Single upload transport only; no runtime wiring, implicit retries or TTL defaults."""

import hashlib
import ipaddress
import json
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .material_readers import MaterialReaders
from .models import BASE_URL
from .network import NetworkError, origin
from .provider import ProviderFailure, classify_http


class UploadError(ValueError):
    pass


@dataclass(frozen=True)
class UploadedReference:
    url: str = field(repr=False)
    file_type: str
    size: int
    expires_in: int | None


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise UploadError("UPLOAD_DUPLICATE_FIELD")
        result[key] = value
    return result


def _constant(value):
    raise UploadError("UPLOAD_NONFINITE_NUMBER")


def decode_upload(body, *, expected_size, expected_type, limit=65536):
    if len(body) > limit:
        raise UploadError("UPLOAD_RESPONSE_LIMIT")
    try:
        data = json.loads(body, object_pairs_hook=_pairs, parse_constant=_constant)
    except UploadError:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise UploadError("UPLOAD_INVALID_JSON") from None
    if not isinstance(data, dict):
        raise UploadError("UPLOAD_INVALID_ENVELOPE")
    url = data.get("url")
    try:
        if not isinstance(url, str) or len(url) > 16384 or origin(url)[0] != "https":
            raise ValueError()
        host = urlsplit(url).hostname
        if not all(host.split(".")):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError()
    except (ValueError, NetworkError):
        raise UploadError("UPLOAD_INVALID_URL") from None
    size, kind, expiry = data.get("size"), data.get("file_type"), data.get("expires_in")
    if type(size) is not int or size <= 0 or size != expected_size:
        raise UploadError("UPLOAD_SIZE_MISMATCH")
    if kind not in ("image", "video", "audio") or kind != expected_type:
        raise UploadError("UPLOAD_TYPE_MISMATCH")
    if expiry is not None and (type(expiry) is not int or not 0 < expiry <= 2147483647):
        raise UploadError("UPLOAD_INVALID_EXPIRY")
    return UploadedReference(url, kind, size, expiry)


_MEDIA = {
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
    ".png": ("image", "image/png"),
    ".webp": ("image", "image/webp"),
    ".mp4": ("video", "video/mp4"),
    ".avi": ("video", "video/x-msvideo"),
    ".mov": ("video", "video/quicktime"),
    ".mkv": ("video", "video/x-matroska"),
    ".mp3": ("audio", "audio/mpeg"),
    ".wav": ("audio", "audio/wav"),
    ".flac": ("audio", "audio/flac"),
}


def _verify(stream, size, digest, limit):
    if type(size) is not int or not 0 < size <= limit:
        raise UploadError("UPLOAD_INPUT_LIMIT")
    stream.seek(0)
    found, total = hashlib.sha256(), 0
    while block := stream.read(65536):
        total += len(block)
        if total > size:
            raise UploadError("UPLOAD_MATERIAL_CHANGED")
        found.update(block)
    if total != size or found.hexdigest() != digest:
        raise UploadError("UPLOAD_MATERIAL_CHANGED")
    stream.seek(0)


async def upload_once(network, stream, *, suffix, expected_size, expected_sha256, byte_limit):
    """Caller owns the registered material lease and locked binary handle throughout.

    No path opening, SQL, generation submission, URL persistence or automatic retry.
    Network policy controls auth, proxy/CA, deadlines and non-idempotent redirects.
    """
    if suffix not in _MEDIA:
        raise UploadError("UPLOAD_FORMAT_UNVERIFIED")
    kind, mime = _MEDIA[suffix]
    await MaterialReaders.thread(_verify, stream, expected_size, expected_sha256, byte_limit)
    status, body = await network.request(
        "POST",
        BASE_URL + "/v1/files/upload",
        phase="upload",
        credential=True,
        limit=65536,
        files={"file": ("material" + suffix, stream, mime)},
    )
    if status != 200:
        failure = classify_http(status, phase="upload", api_id="upload")
        raise ProviderFailure(
            "UPLOAD_REQUEST_REJECTED",
            temporary=status == 429 or 500 <= status <= 599,
            scope=failure.scope,
        )
    return decode_upload(body, expected_size=expected_size, expected_type=kind)
