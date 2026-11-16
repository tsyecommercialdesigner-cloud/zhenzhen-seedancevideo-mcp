"""Check conservative documentation classification and its actual checks."""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("ci_docs", SCRIPTS / "ci_docs.py")
docs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docs)


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ("M\tdocs/guide.md\n", ["docs/guide.md"]),
        ("M\tREADME.md\nM\tsrc/main.py\n", []),
        ("M\tdocs/config.json\n", []),
        ("D\tdocs/guide.md\n", []),
        ("A\tunknown.md\n", []),
    ],
)
def test_classify_by_path_and_status(monkeypatch, change, expected):
    monkeypatch.setattr(docs, "git", lambda *args: change)
    assert docs.eligible("base", "HEAD") == expected


def test_links_and_fences(tmp_path):
    guide = tmp_path / "guide.md"
    (tmp_path / "target.md").write_text("target", encoding="utf-8")
    guide.write_text("[link](target.md)\n\n```python\npass\n```\n", encoding="utf-8")
    docs.check_document(tmp_path, "guide.md")
    guide.write_text("[link](missing.md)\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid local link"):
        docs.check_document(tmp_path, "guide.md")
    guide.write_text("```python\npass\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unclosed"):
        docs.check_document(tmp_path, "guide.md")


def test_dev_document_change_rejects_secret(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output, summary = tmp_path / "out", tmp_path / "summary"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("BASE_REF", "dev")
    monkeypatch.setenv("BASE_SHA", "a" * 40)
    monkeypatch.setattr(docs, "eligible", lambda *args: ["README.md"])
    monkeypatch.setattr(docs, "git", lambda *args: "+sk-" + "x" * 28)
    monkeypatch.setattr(docs.subprocess, "run", lambda *args, **kwargs: None)
    with pytest.raises(ValueError, match="Secret"):
        docs.main()
    assert not output.exists()


def test_release_pr_does_not_use_daily_document_path(tmp_path, monkeypatch):
    output = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("BASE_REF", "main")
    monkeypatch.setenv("BASE_SHA", "a" * 40)
    assert docs.main() == 0
    assert output.read_text().strip() == "docs=false"
