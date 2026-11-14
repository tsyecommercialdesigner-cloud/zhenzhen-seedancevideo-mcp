"""Pure contract validation; no filesystem, database or network side effects."""

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .models import RULE_VERSION, get_model

RATIOS = ("adaptive", "16:9", "9:16", "1:1", "4:3", "3:4", "21:9")
BASE_RESOLUTIONS = ("480p", "720p", "1080p", "2k", "4k")


class ParameterError(ValueError):
    """Static code and field only; never echo prompts or signed URLs."""

    def __init__(self, code, field_name):
        self.code = code
        self.field_name = field_name
        super().__init__(f"{code}: {field_name}")


@dataclass(frozen=True)
class MediaFact:
    """Internal inspection evidence; absent values mean not checked."""

    format: str | None = None
    size_bytes: int | None = None
    duration_seconds: float | None = None


@dataclass(frozen=True)
class DraftFact:
    remote_id: str
    region: str
    is_draft: bool
    completed: bool
    same_account: bool | None = None
    valid: bool | None = None


@dataclass(frozen=True)
class ParameterSnapshot:
    api_id: str
    model_id: str
    explicit_json: str = field(repr=False)
    payload_json: str = field(repr=False)
    unresolved: tuple[str, ...]
    notices: tuple[str, ...]
    rule_version: str = RULE_VERSION

    def payload(self):
        return json.loads(self.payload_json)


def _keys(value, allowed, name):
    if not isinstance(value, dict):
        raise ParameterError("OBJECT_REQUIRED", name)
    if set(value) - set(allowed):
        raise ParameterError("UNKNOWN_OR_INAPPLICABLE_FIELD", name)


def _boolean(value, name):
    if type(value) is not bool:
        raise ParameterError("BOOLEAN_REQUIRED", name)


def _url(value, name):
    if not isinstance(value, str) or any(char.isspace() for char in value):
        raise ParameterError("URL_REQUIRED", name)
    try:
        parsed = urlsplit(value)
        valid = parsed.scheme in ("https", "http") and parsed.hostname and not parsed.username
        _ = parsed.port  # Access validates malformed/out-of-range port values.
    except ValueError:
        valid = False
    if not valid:
        raise ParameterError("URL_REQUIRED", name)
    return value


def resolutions(model):
    if model.kind == "upscale":
        return ("720p", "1080p", "2k", "4k")
    if model.kind == "draft-to-video":
        return ("native1080p",)
    native = ("native1080p",) if model.generation == "2.5" else ()
    if model.generation == "2.0" and model.tier == "standard":
        native = ("native1080p", "native4k")
    return BASE_RESOLUTIONS + native


def normalize(request, *, api_id="seedance-video", media_facts=None, draft_fact=None):
    """Construct a fresh immutable snapshot. Authorization is checked at admission.

    media_facts and draft_fact are internal evidence, never Agent 'verified'
    flags. Unknown remote media properties remain explicitly unverified.
    """
    _keys(
        request, {"model", "prompt", "seconds", "images", "metadata", "enhance_prompt"}, "request"
    )
    try:
        model = get_model(request.get("model"), api_id=api_id)
    except ValueError:
        raise ParameterError("MODEL_NOT_SUPPORTED", "model") from None
    try:
        explicit = json.dumps(request, allow_nan=False, sort_keys=True, separators=(",", ":"))
        payload = json.loads(explicit)
    except (TypeError, ValueError, RecursionError):
        raise ParameterError("INVALID_JSON_VALUE", "request") from None
    metadata = payload.setdefault("metadata", {})
    unresolved = set()
    notices = []
    facts = media_facts or {}
    common = {"resolution", "return_last_frame"}
    allowed = (
        common | {"draft_task_id", "output_format"}
        if model.kind == "draft-to-video"
        else {"resolution", "content"}
        if model.kind == "upscale"
        else common
        | {
            "ratio",
            "generate_audio",
            "duration",
            "seed",
            "content",
            "draft",
            "omni_reference_task_type",
            "video_url",
            "audio_urls",
        }
    )
    _keys(metadata, allowed, "metadata")
    if "enhance_prompt" in payload:
        _boolean(payload["enhance_prompt"], "enhance_prompt")
    if model.kind in ("draft-to-video", "upscale"):
        if any(key in payload for key in ("prompt", "seconds", "images")):
            raise ParameterError("FIELD_NOT_APPLICABLE", "request")
        if payload.pop("enhance_prompt", False):
            raise ParameterError("FIELD_NOT_APPLICABLE", "enhance_prompt")
    if model.kind == "draft-to-video":
        remote_id = metadata.get("draft_task_id")
        if not isinstance(remote_id, str) or not remote_id.strip():
            raise ParameterError("REQUIRED", "metadata.draft_task_id")
        metadata.setdefault("resolution", "native1080p")
        if "output_format" in metadata and metadata["output_format"] not in ("mp4", "mov"):
            raise ParameterError("INVALID_CHOICE", "metadata.output_format")
        if draft_fact is not None:
            if (
                draft_fact.remote_id != remote_id
                or draft_fact.region != model.region
                or not draft_fact.is_draft
                or not draft_fact.completed
                or draft_fact.same_account is False
                or draft_fact.valid is False
            ):
                raise ParameterError("DRAFT_NOT_ELIGIBLE", "metadata.draft_task_id")
        if draft_fact is None:
            unresolved.add("DRAFT_SOURCE_UNVERIFIED")
        if draft_fact is None or draft_fact.same_account is None:
            unresolved.add("DRAFT_ACCOUNT_UNVERIFIED")
        if draft_fact is None or draft_fact.valid is None:
            unresolved.add("DRAFT_VALIDITY_ANCHOR_UNVERIFIED")
    elif model.kind == "upscale":
        metadata.setdefault("resolution", "1080p")
        content = _content(metadata.get("content"))
        if len(content) != 1 or content[0][0] != "video_url":
            raise ParameterError("ONE_VIDEO_REQUIRED", "metadata.content")
        fact = facts.get(content[0][1], MediaFact())
        if fact.format is not None and fact.format.lower() != "mp4":
            raise ParameterError("MP4_REQUIRED", "metadata.content")
        if fact.format is None:
            unresolved.add("INPUT_VIDEO_FORMAT_UNVERIFIED")
        unresolved.add("UPSCALER_EXACT_DURATION_AND_SIZE_UNVERIFIED")
    else:
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ParameterError("REQUIRED", "prompt")
        payload.setdefault("enhance_prompt", False)
        _normal(model, payload, metadata, facts, unresolved, notices)
    if "resolution" in metadata and metadata["resolution"] not in resolutions(model):
        raise ParameterError("INVALID_CHOICE", "metadata.resolution")
    if "return_last_frame" in metadata:
        _boolean(metadata["return_last_frame"], "metadata.return_last_frame")
        unresolved.add("LAST_FRAME_SUPPORT_UNVERIFIED")
    return ParameterSnapshot(
        model.api_id,
        model.model_id,
        explicit,
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        tuple(sorted(unresolved)),
        tuple(notices),
    )


def _content(value):
    if not isinstance(value, list) or not value:
        raise ParameterError("NONEMPTY_CONTENT_REQUIRED", "metadata.content")
    result = []
    for item in value:
        _keys(item, {"type", "image_url", "video_url", "audio_url"}, "metadata.content")
        kind = item.get("type")
        if kind not in ("image_url", "video_url", "audio_url") or set(item) != {"type", kind}:
            raise ParameterError("INVALID_MEDIA_ENTRY", "metadata.content")
        _keys(item[kind], {"url"}, "metadata.content")
        result.append((kind, _url(item[kind].get("url"), "metadata.content")))
    return result


def _normal(model, payload, metadata, facts, unresolved, notices):
    if "duration" in metadata and (
        type(metadata["duration"]) not in (int, float) or metadata["duration"] != -1
    ):
        raise ParameterError("AUTO_DURATION_REQUIRES_MINUS_ONE", "metadata.duration")
    if "duration" in metadata and "seconds" in payload:
        raise ParameterError("DURATION_CONFLICT", "seconds")
    if "seconds" in payload:
        seconds = payload["seconds"]
        high = 30 if model.generation == "2.5" else 15
        if not isinstance(seconds, str) or seconds not in {str(n) for n in range(4, high + 1)}:
            raise ParameterError("INVALID_DURATION", "seconds")
        if model.generation == "2.0":
            unresolved.add("SECONDS_2_0_ENUM_PROVISIONAL")
    metadata.setdefault("generate_audio", True)
    _boolean(metadata["generate_audio"], "metadata.generate_audio")
    if "seed" in metadata:
        if type(metadata["seed"]) not in (int, float) or (
            isinstance(metadata["seed"], float) and not math.isfinite(metadata["seed"])
        ):
            raise ParameterError("FINITE_NUMBER_REQUIRED", "metadata.seed")
        unresolved.add("SEED_RANGE_AND_DEFAULT_UNVERIFIED")
    if "ratio" in metadata:
        allowed = ("adaptive",) if model.generation == "2.5" and model.kind == "i2v" else RATIOS
        if metadata["ratio"] not in allowed:
            raise ParameterError("INVALID_CHOICE", "metadata.ratio")
    if "draft" in metadata:
        if model.generation != "2.5":
            raise ParameterError("FIELD_NOT_APPLICABLE", "metadata.draft")
        _boolean(metadata["draft"], "metadata.draft")
    if model.generation == "2.5":
        metadata.setdefault("draft", False)
    if metadata.get("draft"):
        metadata["resolution"] = "480p"
        notices.append("DRAFT_EFFECTIVE_RESOLUTION_480P")
    if "video_url" in metadata or "audio_urls" in metadata:
        raise ParameterError("CANONICAL_CONTENT_REQUIRED", "metadata")
    if model.kind != "multi" and any(
        k in metadata for k in ("content", "omni_reference_task_type")
    ):
        raise ParameterError("FIELD_NOT_APPLICABLE", "metadata")
    if model.kind == "t2v" and "images" in payload:
        raise ParameterError("FIELD_NOT_APPLICABLE", "images")
    if model.kind == "i2v":
        images = payload.get("images")
        if not isinstance(images, list) or not 1 <= len(images) <= 2:
            raise ParameterError("ONE_OR_TWO_IMAGES_REQUIRED", "images")
        for url in images:
            _image_fact(_url(url, "images"), model, facts, unresolved)
    if model.kind == "multi":
        if "images" in payload:
            raise ParameterError("CANONICAL_CONTENT_REQUIRED", "images")
        content = _content(metadata.get("content"))
        counts = Counter(kind for kind, _ in content)
        maxima = (30, 10, 10) if model.generation == "2.5" else (9, 3, 3)
        if any(
            counts[kind] > limit
            for kind, limit in zip(("image_url", "video_url", "audio_url"), maxima, strict=True)
        ):
            raise ParameterError("TOO_MANY_MEDIA", "metadata.content")
        known_duration = 0
        for kind, url in content:
            if kind == "image_url":
                _image_fact(url, model, facts, unresolved)
                continue
            duration = facts.get(url, MediaFact()).duration_seconds
            if model.generation == "2.5":
                if duration is None:
                    unresolved.add("REFERENCE_DURATION_UNVERIFIED")
                elif not math.isfinite(duration) or not 2 <= duration <= 30:
                    raise ParameterError("INVALID_REFERENCE_DURATION", "metadata.content")
                else:
                    known_duration += duration
            else:
                unresolved.add("REFERENCE_2_0_DURATION_AND_SIZE_UNVERIFIED")
        if known_duration > 30:
            raise ParameterError("REFERENCE_TOTAL_DURATION_EXCEEDED", "metadata.content")
        mode = metadata.get("omni_reference_task_type")
        if "omni_reference_task_type" in metadata:
            if model.generation != "2.5" or mode not in ("edit", "reference", "extend", "auto"):
                raise ParameterError("INVALID_CHOICE", "metadata.omni_reference_task_type")
            if mode in ("edit", "extend") and (
                not counts["video_url"] or metadata.get("ratio") != "adaptive"
            ):
                raise ParameterError("REFERENCE_VIDEO_AND_ADAPTIVE_REQUIRED", "metadata")
            if mode == "edit" and metadata.get("duration") != -1:
                raise ParameterError("EDIT_AUTO_DURATION_REQUIRED", "metadata.duration")


def _image_fact(url, model, facts, unresolved):
    fact = facts.get(url, MediaFact())
    if fact.format is not None and fact.format.lower() not in ("jpg", "jpeg", "png", "webp"):
        raise ParameterError("INVALID_IMAGE_FORMAT", "images")
    if fact.format is None:
        unresolved.add("IMAGE_FORMAT_UNVERIFIED")
    if (
        model.generation == "2.0"
        and model.kind == "i2v"
        and fact.size_bytes is not None
        and fact.size_bytes > 30_000_000
    ):
        raise ParameterError("IMAGE_SIZE_EXCEEDED", "images")
    if fact.size_bytes is None or model.generation == "2.5" or model.kind == "multi":
        unresolved.add("IMAGE_SIZE_UNVERIFIED")
