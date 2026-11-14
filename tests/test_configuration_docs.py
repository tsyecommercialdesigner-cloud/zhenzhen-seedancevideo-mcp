from pathlib import Path

from zhenzhen_seedance_video.config import INT_DEFAULTS, load_configuration

DOCS = Path(__file__).parents[1] / "docs"


def test_example_is_loadable_without_external_credentials(tmp_path):
    root = tmp_path / "installation"
    (root / ".env").write_bytes((DOCS / "configuration.env.example").read_bytes())
    import pytest

    from zhenzhen_seedance_video.config import ConfigurationError

    with pytest.raises(ConfigurationError, match="must not be empty"):
        load_configuration(environ={"LOCALAPPDATA": str(tmp_path)})
    path = root / ".env"
    path.write_text(path.read_text().replace("API_KEY=", "API_KEY=synthetic-doc-key"))
    config = load_configuration(environ={"LOCALAPPDATA": str(tmp_path)})
    assert config.api_key == "synthetic-doc-key"
    assert config.limits["GENERATION_CONCURRENCY"] == 3


def test_documented_defaults_match_configuration():
    document = (DOCS / "configuration.md").read_text(encoding="utf-8")
    for name, value in INT_DEFAULTS.items():
        assert f"| {name} | {value} |" in document
