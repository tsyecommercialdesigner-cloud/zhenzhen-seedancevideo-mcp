"""Versioned exact model registry; model names cannot select arbitrary endpoints."""

from dataclasses import dataclass
from types import MappingProxyType

RULE_VERSION = "seedance-contract-2026-11-13.1"
BASE_URL = "https://api.seedance.nz"
SUBMIT_PATH = "/v1/video/generations"
QUERY_PATH = "/v1/video/generations/{id}"


@dataclass(frozen=True)
class Model:
    model_id: str
    api_id: str
    generation: str
    region: str
    tier: str
    kind: str
    rule_version: str = RULE_VERSION


def _registry():
    entries = {}
    for generation, tiers in (("2.0", ("standard", "fast", "mini")), ("2.5", ("standard",))):
        for prefix, region in (("", "domestic"), ("global-", "global")):
            for tier in tiers:
                kinds = ("t2v", "i2v", "multi")
                if generation == "2.5":
                    kinds += ("draft-to-video",)
                for kind in kinds:
                    name = f"seedance-{generation}-{prefix}{tier}-{kind}"
                    entries[name] = Model(name, "seedance-video", generation, region, tier, kind)
    return MappingProxyType(entries)


VIDEO_MODELS = _registry()
UPSCALER = Model(
    "zhenzhen-upscaler", "zhenzhen-upscaler", "independent", "provider", "upscale", "upscale"
)


def get_model(model_id: str, *, api_id: str = "seedance-video") -> Model:
    if api_id == "zhenzhen-upscaler" and model_id == UPSCALER.model_id:
        return UPSCALER
    if api_id == "seedance-video" and isinstance(model_id, str) and model_id in VIDEO_MODELS:
        return VIDEO_MODELS[model_id]
    raise ValueError("MODEL_NOT_SUPPORTED")
