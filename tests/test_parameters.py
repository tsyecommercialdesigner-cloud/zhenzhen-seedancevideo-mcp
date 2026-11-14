import json

import pytest

from zhenzhen_seedance_video.models import VIDEO_MODELS
from zhenzhen_seedance_video.parameters import DraftFact, MediaFact, ParameterError, normalize


def media(kind="video_url", url="https://example.test/input"):
    return {"type": kind, kind: {"url": url}}


def request(model="seedance-2.5-standard-t2v", **metadata):
    result = {"model": model, "prompt": "test", "metadata": metadata}
    if model.endswith("-i2v"):
        result["images"] = ["https://example.test/image"]
    if model.endswith("-multi"):
        result["metadata"].setdefault("content", [media()])
    return result


@pytest.mark.parametrize("model", [m for m in VIDEO_MODELS if not m.endswith("draft-to-video")])
def test_all_normal_models_keep_known_defaults_and_unknown_omissions(model):
    snapshot = normalize(request(model))
    effective = snapshot.payload()
    assert effective["model"] == model
    assert effective["metadata"]["generate_audio"] is True
    assert effective["enhance_prompt"] is False
    assert "seconds" not in effective
    assert "ratio" not in effective["metadata"]
    assert "seed" not in effective["metadata"]
    assert snapshot.rule_version


@pytest.mark.parametrize(
    "model,resolution,accepted",
    [
        ("seedance-2.0-standard-t2v", "native4k", True),
        ("seedance-2.0-mini-t2v", "native1080p", False),
        ("seedance-2.0-global-fast-t2v", "native4k", False),
        ("seedance-2.5-standard-t2v", "native4k", False),
        ("seedance-2.5-standard-t2v", "native1080p", True),
    ],
)
def test_resolution_matrix(model, resolution, accepted):
    if accepted:
        assert (
            normalize(request(model, resolution=resolution)).payload()["metadata"]["resolution"]
            == resolution
        )
    else:
        with pytest.raises(ParameterError):
            normalize(request(model, resolution=resolution))


def test_i2v_ratio_conflict_and_media_order():
    with pytest.raises(ParameterError, match="ratio"):
        normalize(request("seedance-2.5-standard-i2v", ratio="16:9"))
    value = request("seedance-2.5-standard-i2v", ratio="adaptive")
    value["images"].append("https://example.test/last")
    assert normalize(value).payload()["images"] == value["images"]
    value["images"].append("https://example.test/third")
    with pytest.raises(ParameterError):
        normalize(value)


def test_auto_duration_and_provisional_2_0_range():
    value = request(duration=-1)
    assert "seconds" not in normalize(value).payload()
    value["seconds"] = "5"
    with pytest.raises(ParameterError, match="DURATION_CONFLICT"):
        normalize(value)
    value = request("seedance-2.0-mini-t2v") | {"seconds": "15"}
    assert "SECONDS_2_0_ENUM_PROVISIONAL" in normalize(value).unresolved
    for invalid in ("-1", "16", "5.0", 5, True):
        with pytest.raises(ParameterError):
            normalize(value | {"seconds": invalid})
    assert normalize(request() | {"seconds": "30"}).payload()["seconds"] == "30"


@pytest.mark.parametrize(
    "version,kind,limit",
    [
        ("2.0", "image_url", 9),
        ("2.0", "video_url", 3),
        ("2.0", "audio_url", 3),
        ("2.5", "image_url", 30),
        ("2.5", "video_url", 10),
        ("2.5", "audio_url", 10),
    ],
)
def test_media_limits_and_order(version, kind, limit):
    content = [media(kind, f"https://example.test/{i}") for i in range(limit)]
    value = request(f"seedance-{version}-standard-multi", content=content)
    assert normalize(value).payload()["metadata"]["content"] == content
    content.append(media(kind))
    with pytest.raises(ParameterError, match="TOO_MANY_MEDIA"):
        normalize(value)


def test_canonical_content_and_wrong_mode_fields_rejected():
    value = request("seedance-2.0-mini-multi")
    with pytest.raises(ParameterError, match="CANONICAL_CONTENT"):
        normalize(value | {"images": ["https://example.test/a"]})
    with pytest.raises(ParameterError):
        normalize(request(content=[media()]))
    with pytest.raises(ParameterError):
        normalize(request("seedance-2.0-mini-i2v", audio_urls=["https://example.test/a"]))


def test_reference_duration_known_unknown_and_total():
    a, b = "https://example.test/a", "https://example.test/b"
    value = request("seedance-2.5-standard-multi", content=[media(url=a), media("audio_url", b)])
    assert "REFERENCE_DURATION_UNVERIFIED" in normalize(value).unresolved
    with pytest.raises(ParameterError, match="TOTAL_DURATION"):
        normalize(
            value,
            media_facts={a: MediaFact(duration_seconds=20), b: MediaFact(duration_seconds=20)},
        )
    with pytest.raises(ParameterError, match="INVALID_REFERENCE_DURATION"):
        normalize(value, media_facts={a: MediaFact(duration_seconds=1)})
    assert (
        "REFERENCE_DURATION_UNVERIFIED"
        not in normalize(
            value,
            media_facts={a: MediaFact(duration_seconds=10), b: MediaFact(duration_seconds=20)},
        ).unresolved
    )


def test_edit_and_extend_are_not_inferred_or_conflated():
    value = request(
        "seedance-2.5-standard-multi", omni_reference_task_type="edit", ratio="adaptive"
    )
    with pytest.raises(ParameterError, match="EDIT_AUTO"):
        normalize(value)
    value["metadata"]["duration"] = -1
    normalize(value)
    value["metadata"].pop("duration")
    value["metadata"]["omni_reference_task_type"] = "extend"
    assert "duration" not in normalize(value).payload()["metadata"]
    value["metadata"]["content"] = [media("image_url")]
    with pytest.raises(ParameterError, match="REFERENCE_VIDEO"):
        normalize(value)
    plain = request("seedance-2.5-standard-multi") | {"prompt": "Replace the person in @Video 1"}
    assert "omni_reference_task_type" not in normalize(plain).payload()["metadata"]


def test_image_inspection_evidence_and_seed_types():
    value = request("seedance-2.0-mini-i2v", seed=1.5)
    assert "SEED_RANGE_AND_DEFAULT_UNVERIFIED" in normalize(value).unresolved
    url = value["images"][0]
    with pytest.raises(ParameterError, match="IMAGE_SIZE"):
        normalize(value, media_facts={url: MediaFact("png", 30_000_001)})
    with pytest.raises(ParameterError, match="IMAGE_FORMAT"):
        normalize(value, media_facts={url: MediaFact("gif", 1)})
    with pytest.raises(ParameterError):
        normalize(request(seed=True))


def test_draft_effective_resolution_and_snapshot_immutability():
    value = request(draft=True, resolution="4k")
    snapshot = normalize(value)
    assert snapshot.payload()["metadata"]["resolution"] == "480p"
    assert json.loads(snapshot.explicit_json)["metadata"]["resolution"] == "4k"
    assert "DRAFT_EFFECTIVE_RESOLUTION_480P" in snapshot.notices
    value["metadata"]["resolution"] = "720p"
    copy = snapshot.payload()
    copy["metadata"]["resolution"] = "720p"
    assert snapshot.payload()["metadata"]["resolution"] == "480p"
    with pytest.raises(ParameterError):
        normalize(request("seedance-2.0-mini-t2v", draft=True))


@pytest.mark.parametrize("prefix,region", [("", "domestic"), ("global-", "global")])
def test_draft_final_inheritance_and_known_invalid(prefix, region):
    value = {
        "model": f"seedance-2.5-{prefix}standard-draft-to-video",
        "metadata": {"draft_task_id": "d"},
    }
    snapshot = normalize(value)
    assert snapshot.payload()["metadata"] == {"draft_task_id": "d", "resolution": "native1080p"}
    assert "DRAFT_ACCOUNT_UNVERIFIED" in snapshot.unresolved
    for fact in (
        DraftFact("d", "other", True, True),
        DraftFact("d", region, False, True),
        DraftFact("d", region, True, False),
        DraftFact("d", region, True, True, False),
        DraftFact("d", region, True, True, True, False),
    ):
        with pytest.raises(ParameterError, match="DRAFT_NOT_ELIGIBLE"):
            normalize(value, draft_fact=fact)
    value["metadata"].update(return_last_frame=False, output_format="mov")
    assert normalize(value).payload()["metadata"]["return_last_frame"] is False
    for key, val in (("prompt", "x"), ("seconds", "5"), ("enhance_prompt", True)):
        with pytest.raises(ParameterError):
            normalize(value | {key: val})


def test_independent_upscaler():
    value = {
        "model": "zhenzhen-upscaler",
        "metadata": {"content": [media()]},
        "enhance_prompt": False,
    }
    snapshot = normalize(value, api_id="zhenzhen-upscaler")
    assert snapshot.payload()["metadata"]["resolution"] == "1080p"
    assert not {"prompt", "seconds", "enhance_prompt"} & snapshot.payload().keys()
    assert "UPSCALER_EXACT_DURATION_AND_SIZE_UNVERIFIED" in snapshot.unresolved
    with pytest.raises(ParameterError, match="MP4_REQUIRED"):
        normalize(
            value,
            api_id="zhenzhen-upscaler",
            media_facts={"https://example.test/input": MediaFact("mov")},
        )
    value["metadata"]["content"].append(media())
    with pytest.raises(ParameterError, match="ONE_VIDEO"):
        normalize(value, api_id="zhenzhen-upscaler")


@pytest.mark.parametrize(
    "change",
    [
        {"extra": 1},
        {"metadata": {"typo": True}},
        {"prompt": ""},
        {"metadata": {"generate_audio": "true"}},
        {"metadata": None},
    ],
)
def test_unknown_and_malformed_fields(change):
    with pytest.raises(ParameterError):
        normalize(request() | change)
