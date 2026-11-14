"""Decode evidence-backed compatibility envelopes without recursive field discovery."""

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from .charges import ActualCharge


class ResponseError(ValueError):
    """Only static codes may escape this boundary, never response contents."""


@dataclass(frozen=True)
class Observation:
    remote_id: str
    model: str
    status: Literal["queued", "in_progress", "completed", "failed"]
    progress: int | float | None
    video_url: str | None = field(repr=False)
    error_code: str | None
    attention: str | None
    usage_verified: bool = False
    charge: ActualCharge | None = None
    provider_status: str | None = None
    last_frame_url: str | None = field(default=None, repr=False)
    draft_task_id: str | None = None


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ResponseError("DUPLICATE_RESPONSE_FIELD")
        result[key] = value
    return result


def _constant(value):
    raise ResponseError("NONFINITE_RESPONSE_NUMBER")


def decode_response(
    body: bytes,
    *,
    expected_model: str,
    expected_id: str | None = None,
    limit: int = 2 * 1024 * 1024,
) -> Observation:
    """Return observed facts, without inferring acceptance from HTTP status.

    Missing/invalid download URLs preserve the confirmed successful outcome,
    with attention required. URL network safety belongs to the downloader.
    Progress is observational; it never determines the outcome.
    """
    if len(body) > limit:
        raise ResponseError("RESPONSE_TOO_LARGE")
    try:
        data = json.loads(
            body, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=Decimal
        )
    except ResponseError:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise ResponseError("INVALID_RESPONSE_JSON") from None
    if not isinstance(data, dict):
        raise ResponseError("INVALID_RESPONSE_ENVELOPE")
    charge = None
    last_frame_url = None
    draft_task_id = None
    provider_status = data.get("status")
    envelope = data.get("code") == "success" and isinstance(data.get("data"), dict)
    if envelope:
        nested = data["data"]
        provider_status = nested.get("status")
        if expected_id is None:
            raise ResponseError("QUERY_ID_REQUIRED")
        if nested.get("status") not in ("NOT_START", "IN_PROGRESS", "SUCCESS"):
            raise ResponseError("REMOTE_STATUS_UNVERIFIED")
        properties = nested.get("properties")
        if (
            not isinstance(properties, dict)
            or properties.get("origin_model_name") != expected_model
        ):
            raise ResponseError("RESPONSE_IDENTITY_MISMATCH")
        progress = nested.get("progress")
        if progress is not None:
            if not isinstance(progress, str) or not re.fullmatch(r"(?:100|[0-9]{1,2})%", progress):
                raise ResponseError("INVALID_REMOTE_PROGRESS")
            progress = int(progress[:-1])
        if nested["status"] == "SUCCESS" and "usage" in nested:
            usage = nested["usage"]
            if not isinstance(usage, dict):
                raise ResponseError("INVALID_ACTUAL_USAGE")
            amount = usage.get("amount")
            if amount is not None and type(amount) not in (int, Decimal):
                raise ResponseError("INVALID_ACTUAL_AMOUNT")
            try:
                charge = ActualCharge(
                    Decimal(amount) if amount is not None else None,
                    usage.get("currency"),
                    "SUCCESS",
                    hashlib.sha256(body).hexdigest(),
                )
            except ValueError:
                raise ResponseError("INVALID_ACTUAL_USAGE") from None
        if nested["status"] == "SUCCESS":
            inner = nested.get("data")
            content = inner.get("content") if isinstance(inner, dict) else None
            if (
                expected_model.startswith("seedance-2.5-")
                and expected_model.endswith(("-t2v", "-i2v", "-multi"))
                and isinstance(content, dict)
                and content.get("draft") is True
                and "draft_task_id" in content
            ):
                draft_task_id = content["draft_task_id"]
                if not isinstance(draft_task_id, str) or draft_task_id != expected_id:
                    raise ResponseError("DRAFT_TASK_ID_MISMATCH")
            candidate = content.get("last_frame_url") if isinstance(content, dict) else None
            if isinstance(candidate, str):
                try:
                    parsed = urlsplit(candidate)
                    if (
                        parsed.scheme == "https"
                        and parsed.hostname
                        and not parsed.username
                        and not parsed.password
                        and not any(c.isspace() for c in candidate)
                    ):
                        last_frame_url = candidate
                except ValueError:
                    pass
        data = {
            "id": nested.get("task_id"),
            "object": "video",
            "model": expected_model,
            "status": {
                "NOT_START": "queued",
                "IN_PROGRESS": "in_progress",
                "SUCCESS": "completed",
            }[nested["status"]],
            "progress": progress,
            "metadata": {"url": nested.get("result_url")},
        }
    elif data.get("status") == "SUCCESS" or (
        isinstance(data.get("data"), dict) and data["data"].get("status") == "SUCCESS"
    ):
        raise ResponseError("SUCCESS_ENVELOPE_UNVERIFIED")
    if "task_id" in data and data["task_id"] != data.get("id"):
        raise ResponseError("REMOTE_ID_MISMATCH")
    remote_id = data.get("id")
    if not isinstance(remote_id, str) or not remote_id.strip() or len(remote_id) > 512:
        raise ResponseError("INVALID_REMOTE_ID")
    if expected_id is not None and remote_id != expected_id:
        raise ResponseError("REMOTE_ID_MISMATCH")
    if data.get("object") != "video" or data.get("model") != expected_model:
        raise ResponseError("RESPONSE_IDENTITY_MISMATCH")
    status = data.get("status")
    if status not in ("queued", "in_progress", "completed", "failed"):
        raise ResponseError("REMOTE_STATUS_UNVERIFIED")
    progress = data.get("progress")
    if progress is not None and (
        type(progress) not in (int, float, Decimal)
        or (isinstance(progress, float) and not math.isfinite(progress))
    ):
        raise ResponseError("INVALID_REMOTE_PROGRESS")
    if isinstance(progress, Decimal):
        progress = float(progress)
        if not math.isfinite(progress):
            raise ResponseError("INVALID_REMOTE_PROGRESS")
    video_url = None
    attention = None
    if status == "completed":
        metadata = data.get("metadata")
        candidate = metadata.get("url") if isinstance(metadata, dict) else None
        try:
            parsed = urlsplit(candidate) if isinstance(candidate, str) else None
            valid = (
                parsed is not None
                and parsed.scheme == "https"
                and parsed.hostname
                and not parsed.username
                and not parsed.password
                and not any(character.isspace() for character in candidate)
            )
            if valid:
                video_url = candidate
        except ValueError:
            pass
        if video_url is None:
            attention = "RESULT_URL_UNAVAILABLE"
    # Do not expose upstream free text or unknown error codes as Agent instructions.
    error_code = None
    if status == "failed":
        error = data.get("error")
        error_code = (
            "video_generation_failed"
            if isinstance(error, dict) and error.get("code") == "video_generation_failed"
            else "REMOTE_TASK_FAILED"
        )
    return Observation(
        remote_id,
        expected_model,
        status,
        progress,
        video_url,
        error_code,
        attention,
        charge is not None,
        charge,
        provider_status,
        last_frame_url,
        draft_task_id,
    )
