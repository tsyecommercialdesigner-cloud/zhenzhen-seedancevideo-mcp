import pytest

from zhenzhen_seedance_video.models import UPSCALER, VIDEO_MODELS, get_model

EXPECTED = """
seedance-2.5-global-standard-draft-to-video
seedance-2.5-standard-draft-to-video
seedance-2.5-global-standard-t2v
seedance-2.5-global-standard-i2v
seedance-2.5-global-standard-multi
seedance-2.5-standard-t2v
seedance-2.5-standard-i2v
seedance-2.5-standard-multi
seedance-2.0-global-fast-t2v
seedance-2.0-global-fast-i2v
seedance-2.0-global-fast-multi
seedance-2.0-fast-t2v
seedance-2.0-fast-i2v
seedance-2.0-fast-multi
seedance-2.0-global-mini-t2v
seedance-2.0-global-mini-i2v
seedance-2.0-global-mini-multi
seedance-2.0-mini-t2v
seedance-2.0-mini-i2v
seedance-2.0-mini-multi
seedance-2.0-global-standard-t2v
seedance-2.0-global-standard-i2v
seedance-2.0-global-standard-multi
seedance-2.0-standard-t2v
seedance-2.0-standard-i2v
seedance-2.0-standard-multi
""".split()


def test_exact_whitelist_and_separate_upscaler():
    assert len(VIDEO_MODELS) == 26
    assert set(VIDEO_MODELS) == set(EXPECTED)
    assert UPSCALER.model_id not in VIDEO_MODELS
    assert get_model("zhenzhen-upscaler", api_id="zhenzhen-upscaler") == UPSCALER


@pytest.mark.parametrize("model_id", EXPECTED)
def test_model_dimensions(model_id):
    model = get_model(model_id)
    assert model.model_id == model_id
    assert model.generation in ("2.0", "2.5")
    assert f"seedance-{model.generation}-" in model_id
    assert (model.region == "global") == ("-global-" in model_id)
    assert f"-{model.tier}-" in model_id
    assert model_id.endswith("-" + model.kind)
    assert model.api_id == "seedance-video"
    assert model.rule_version


@pytest.mark.parametrize(
    "model_id,api_id",
    [
        ("zhenzhen-upscaler", "seedance-video"),
        (EXPECTED[0], "zhenzhen-upscaler"),
        ("seedance-2.0-pro-t2v", "seedance-video"),
        ("https://other.example", "http"),
    ],
)
def test_no_cross_api_or_unknown_model(model_id, api_id):
    with pytest.raises(ValueError, match="MODEL_NOT_SUPPORTED"):
        get_model(model_id, api_id=api_id)
