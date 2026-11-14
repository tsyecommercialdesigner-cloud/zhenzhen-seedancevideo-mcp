import json

import pytest

from zhenzhen_seedance_video.config import load_configuration
from zhenzhen_seedance_video.models import VIDEO_MODELS
from zhenzhen_seedance_video.parameters import ParameterError, normalize
from zhenzhen_seedance_video.preflight import (
    OBSERVED_MODELS,
    capabilities,
    preflight,
    restore_snapshot,
    serialize_snapshot,
)


@pytest.mark.parametrize("model_id", VIDEO_MODELS)
def test_each_model_capability_matches_identity_and_constraints(model_id):
    result = capabilities(api_id="seedance-video", model_id=model_id)
    assert result["model_id"] == model_id
    expected = "observed_partial" if model_id in OBSERVED_MODELS else "unverified"
    assert result["operations"]["success_envelope"] == expected
    assert result["operations"]["actual_charge_envelope"] == expected
    assert result["real_provider_validation"] == (
        "partial" if model_id in OBSERVED_MODELS else "not_performed"
    )
    assert result["arbitrary_http"] == "unsupported"
    if "-2.5-" in model_id and model_id.endswith("i2v"):
        assert result["ratios"] == ["adaptive"]
    assert "native4k" not in result["resolutions"] or (
        "-2.0-" in model_id and "-standard-" in model_id
    )


def test_preflight_has_no_task_files_or_network(tmp_path):
    config = load_configuration(
        environ={"LOCALAPPDATA": str(tmp_path), "ZHENZHEN_SEEDANCE_API_KEY": "synthetic-key"}
    )
    before = list(tmp_path.rglob("*"))
    result = preflight(
        {"model": "seedance-2.5-standard-t2v", "prompt": "test"}, configuration=config
    )
    assert result["ok"]
    assert result["admission_guaranteed"] is False
    assert result["estimated_charge"] is None
    assert "synthetic-key" not in json.dumps(result)
    assert list(tmp_path.rglob("*")) == before


def test_snapshot_restoration_does_not_run_new_normalization(monkeypatch):
    snapshot = normalize({"model": "seedance-2.5-standard-t2v", "prompt": "test"})
    stored = serialize_snapshot(snapshot)
    monkeypatch.setattr("zhenzhen_seedance_video.preflight.normalize", lambda *a, **k: None)
    assert restore_snapshot(stored) == snapshot
    changed = json.loads(stored)
    changed["rule_version"] = "future"
    with pytest.raises(ParameterError, match="SNAPSHOT_RULE_UNSUPPORTED"):
        restore_snapshot(json.dumps(changed))


def test_summary_and_upscaler_are_separate():
    assert len(capabilities()["apis"]) == 2
    assert len(capabilities(api_id="seedance-video")["models"]) == 26
    upscale = capabilities(api_id="zhenzhen-upscaler", model_id="zhenzhen-upscaler")
    assert upscale["enhance_prompt"] == "not_applicable"
    assert upscale["defaults"] == {"metadata.resolution": "1080p"}
    assert upscale["real_provider_validation"] == "partial"
    assert capabilities(api_id="seedance-video")["operations"]["success_envelope"] == "unverified"
