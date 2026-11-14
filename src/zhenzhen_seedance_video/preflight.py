"""Read-only capability and local preflight services, independent of MCP transport."""

import json
from dataclasses import asdict

from .config import Configuration
from .models import RULE_VERSION, UPSCALER, VIDEO_MODELS, get_model
from .parameters import RATIOS, ParameterError, ParameterSnapshot, normalize, resolutions

UNVERIFIED_OPERATIONS = (
    "remote_cancel",
    "submission_lookup",
    "account_identity",
    "artifact_url_refresh",
)

OBSERVED_MODELS = frozenset(
    {
        "seedance-2.0-mini-t2v",
        "seedance-2.0-mini-i2v",
        "seedance-2.0-global-fast-i2v",
        "seedance-2.0-standard-multi",
        "seedance-2.5-standard-t2v",
        "seedance-2.5-standard-draft-to-video",
        "seedance-2.5-global-standard-t2v",
        "seedance-2.5-global-standard-draft-to-video",
        "zhenzhen-upscaler",
    }
)


def _operations(model_id=None):
    observed = model_id in OBSERVED_MODELS if model_id else False
    status = "observed_partial" if observed else "unverified"
    return {key: "unverified" for key in UNVERIFIED_OPERATIONS} | {
        "success_envelope": status,
        "actual_charge_envelope": status,
    }


def capabilities(*, api_id=None, model_id=None):
    if api_id is None:
        if model_id is not None:
            raise ParameterError("API_ID_REQUIRED", "api_id")
        return {
            "rule_version": RULE_VERSION,
            "apis": [
                {"api_id": "seedance-video", "model_count": 26},
                {"api_id": "zhenzhen-upscaler", "model_count": 1},
            ],
        }
    if api_id not in ("seedance-video", "zhenzhen-upscaler"):
        raise ParameterError("API_NOT_SUPPORTED", "api_id")
    if model_id is None:
        return {
            "api_id": api_id,
            "rule_version": RULE_VERSION,
            "models": list(VIDEO_MODELS) if api_id == "seedance-video" else [UPSCALER.model_id],
            "operations": _operations(),
            "provider_evidence": "partial_model_observations; cross_model_unverified",
        }
    model = get_model(model_id, api_id=api_id)
    result = asdict(model) | {
        "resolutions": list(resolutions(model)),
        "operations": _operations(model_id),
        "arbitrary_http": "unsupported",
        "real_provider_validation": "partial" if model_id in OBSERVED_MODELS else "not_performed",
    }
    if model.kind == "draft-to-video":
        result.update(
            required=["model", "metadata.draft_task_id"],
            optional=[
                "metadata.resolution",
                "metadata.output_format",
                "metadata.return_last_frame",
            ],
            defaults={"metadata.resolution": "native1080p"},
            output_formats=["mp4", "mov"],
            draft_requirements={
                "same_account": True,
                "same_region": True,
                "completed_draft": True,
                "validity_days": 7,
                "expiry_anchor": "unverified",
            },
            omitted_last_frame="inherit",
            enhance_prompt="not_applicable",
        )
    elif model.kind == "upscale":
        result.update(
            required=["model", "metadata.content"],
            optional=["metadata.resolution"],
            defaults={"metadata.resolution": "1080p"},
            media={
                "video_url": 1,
                "format": "mp4",
                "duration_approx_minutes": 10,
                "exact_duration_and_size": "unverified",
            },
            enhance_prompt="not_applicable",
        )
    else:
        optional = [
            "seconds",
            "metadata.duration",
            "metadata.resolution",
            "metadata.ratio",
            "metadata.generate_audio",
            "metadata.seed",
            "metadata.return_last_frame",
            "enhance_prompt",
        ]
        required = ["model", "prompt"]
        if model.kind == "i2v":
            required.append("images")
        elif model.kind == "multi":
            required.append("metadata.content")
        defaults = {"metadata.generate_audio": True, "enhance_prompt": False}
        if model.generation == "2.5":
            optional.append("metadata.draft")
            defaults["metadata.draft"] = False
            if model.kind == "multi":
                optional.append("metadata.omni_reference_task_type")
        result.update(
            required=required,
            optional=optional,
            defaults=defaults,
            seconds={
                "minimum": 4,
                "maximum": 30 if model.generation == "2.5" else 15,
                "type": "integer_string",
                "status": "confirmed" if model.generation == "2.5" else "provisional",
            },
            auto_duration={"metadata.duration": -1, "seconds": "must_be_omitted"},
            ratios=["adaptive"]
            if model.generation == "2.5" and model.kind == "i2v"
            else list(RATIOS),
            seed={"type": "number", "range_and_default": "unverified"},
            last_frame_support="unverified",
            enhance_prompt="authorization_required_for_true",
        )
        if model.kind == "i2v":
            result["media"] = {
                "images_min": 1,
                "images_max": 2,
                "formats": ["jpg", "png", "webp"],
                "size_limit_bytes": 30_000_000 if model.generation == "2.0" else "unverified",
            }
        elif model.kind == "multi":
            result["media"] = {
                "maxima": [30, 10, 10] if model.generation == "2.5" else [9, 3, 3],
                "order": ["image_url", "video_url", "audio_url"],
                "aliases": "unsupported",
            }
            if model.generation == "2.5":
                result["media"].update(av_seconds_min=2, av_seconds_max=30, av_seconds_total_max=30)
                result["modes"] = {
                    "edit": ["reference_video", "adaptive", "auto_duration"],
                    "extend": ["reference_video", "adaptive"],
                    "reference": [],
                    "auto": [],
                }
            else:
                result["media"]["duration_and_size"] = "unverified"
    return result


def preflight(
    request,
    *,
    configuration: Configuration,
    api_id="seedance-video",
    media_facts=None,
    draft_fact=None,
):
    snapshot = normalize(request, api_id=api_id, media_facts=media_facts, draft_fact=draft_fact)
    return {
        "ok": True,
        "scope": "local_contract_checks",
        "rule_version": snapshot.rule_version,
        "api_id": snapshot.api_id,
        "model": snapshot.model_id,
        "effective_parameters": snapshot.payload(),
        "unverified": list(snapshot.unresolved),
        "notices": list(snapshot.notices),
        "output_dir": str(configuration.output_dir),
        "configuration": "loaded",
        "admission_guaranteed": False,
        "authorization_checked": False,
        "estimated_charge": None,
    }


def serialize_snapshot(snapshot: ParameterSnapshot):
    return json.dumps(asdict(snapshot), sort_keys=True, separators=(",", ":"))


def restore_snapshot(serialized: str):
    """Restore trusted persisted values without reapplying current defaults."""
    data = json.loads(serialized)
    if data.get("rule_version") != RULE_VERSION:
        raise ParameterError("SNAPSHOT_RULE_UNSUPPORTED", "rule_version")
    data["unresolved"] = tuple(data["unresolved"])
    data["notices"] = tuple(data["notices"])
    return ParameterSnapshot(**data)
