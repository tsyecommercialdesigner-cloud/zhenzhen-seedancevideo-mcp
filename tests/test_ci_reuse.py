"""Candidate reuse must fail closed and report its actual scope."""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("ci_reuse", SCRIPTS / "ci_reuse.py")
reuse = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reuse)


@pytest.mark.parametrize("trusted", [123, None])
def test_candidate_requires_verified_identical_tree(tmp_path, monkeypatch, trusted):
    output, summary = tmp_path / "output", tmp_path / "summary"
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/repo")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setattr(reuse, "current_evidence", lambda: {"repository": "example/repo"})
    monkeypatch.setattr(reuse, "git", lambda *args: "a" * 40)

    def trusted_run(repository, target, expected, exact_tree):
        assert (repository, target, exact_tree) == ("example/repo", "HEAD", "a" * 40)
        return trusted

    monkeypatch.setattr(reuse, "trusted_run", trusted_run)
    assert reuse.main() == 0
    lines = output.read_text().splitlines()
    assert lines[0] == f"reuse={'true' if trusted else 'false'}"
    assert lines[1:] == (["reuse_run=123"] if trusted else [])
    assert ("trusted run 123" if trusted else "full checks required") in summary.read_text()


def test_missing_evidence_falls_back(tmp_path, monkeypatch):
    output, summary = tmp_path / "output", tmp_path / "summary"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    def unavailable():
        raise RuntimeError("offline")

    monkeypatch.setattr(reuse, "current_evidence", unavailable)
    assert reuse.main() == 0
    assert output.read_text().strip() == "reuse=false"
