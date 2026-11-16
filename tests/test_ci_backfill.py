"""Conservative classification and trusted evidence verification."""

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

scripts = str(Path(__file__).resolve().parents[1] / "scripts")
sys.path.insert(0, scripts)
spec = importlib.util.spec_from_file_location("ci_backfill", Path(scripts) / "ci_backfill.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def test_fact_paragraph_does_not_allow_unrelated_edits():
    old = "当前版本 **0.1.0.dev0**。本地生命周期保持不变。"
    new = (
        "当前版本 **0.1.0.dev1**，已发布为[开发预发行版]"
        "(https://github.com/tsyecommercialdesigner-cloud/"
        "zhenzhen-seedancevideo-mcp/releases/tag/v0.1.0.dev1)，"
        "标签提交 `" + "a" * 40 + "`。本地生命周期保持不变。"
    )
    assert gate._markdown_release_paragraphs(old, new, "README.md")
    assert not gate._markdown_release_paragraphs(old, new + "执行其他操作。", "README.md")
    assert not gate._markdown_release_paragraphs(
        old, new.replace("标签提交", "跳过检查；标签提交"), "README.md"
    )
    assert not gate._markdown_release_paragraphs(old, new + "\n```\ncommand\n```", "README.md")


def test_json_only_explicit_release_asset_records():
    old = json.dumps([{"legacy": "preserved"}])
    row = {
        "path": "https://example.invalid/file.whl",
        "purpose": "published-release-asset",
        "version": "v0.1.0.dev1",
        "task": "release-fact-backfill",
        "owner": "release owner",
        "status": "published",
        "sha256": "a" * 64,
        "release_condition": "retain published asset",
        "cleanup": "do not delete published asset",
    }
    assert gate._resource_records(old, json.dumps([{"legacy": "preserved"}, row]))
    assert not gate._resource_records(old, json.dumps([{"legacy": "changed"}, row]))
    assert not gate._resource_records(
        old, json.dumps([{"legacy": "preserved"}, {**row, "run": "x"}])
    )
    assert not gate._release_records("old", "old\n## 2026-01-01 发布\narbitrary")


def test_evidence_requires_matching_environment_and_trusted_merged_pr():
    expected = {
        "schema": 1,
        "scope": "full-windows-lint-format-tests-build",
        "operational_inputs_sha256": "f" * 64,
        "excluded_passive_fact_files": sorted(gate.PASSIVE_FACT_FILES),
        "repository": "example/repo",
        "python": "3.12.14",
        "uv": "uv 0.12.9",
        "git": "git version 2.0",
        "gh": "gh version 2.0",
        "runner_os": "Windows",
        "runner_arch": "X64",
        "image_os": "win22",
        "image_version": "version-1",
    }
    evidence = {
        **expected,
        "run_id": "123",
        "run_attempt": "1",
        "event": "pull_request",
        "workflow_ref": "example/repo/.github/workflows/pr-checks.yml@refs/pull/1/merge",
        "source_commit": "a" * 40,
        "source_tree": "b" * 40,
    }
    run = {
        "id": 123,
        "run_attempt": 1,
        "head_sha": "c" * 40,
        "status": "completed",
        "conclusion": "success",
        "event": "pull_request",
    }
    pull = {
        "merged": True,
        "head": {"sha": "c" * 40, "repo": {"full_name": "example/repo"}},
        "base": {"ref": "dev"},
    }
    assert gate.evidence_matches(evidence, expected, run, pull, True)
    assert not gate.evidence_matches(evidence, expected, run, pull, False)
    assert not gate.evidence_matches(
        evidence, {**expected, "image_version": "different"}, run, pull, True
    )
    assert not gate.evidence_matches(
        evidence, expected, {**run, "conclusion": "failure"}, pull, True
    )
    assert not gate.evidence_matches(evidence, expected, run, {**pull, "merged": False}, True)
    assert not gate.evidence_matches(evidence, expected, {**run, "event": "push"}, pull, True)
    assert not gate.evidence_matches(evidence, expected, {**run, "run_attempt": 2}, pull, True)
    fork = {**pull, "head": {"sha": "c" * 40, "repo": {"full_name": "fork/repo"}}}
    assert not gate.evidence_matches(evidence, expected, run, fork, True)


@pytest.mark.parametrize(
    "value", ["https://host.invalid/path?X-Tos-" + "Signature=secret", "sk-" + "x" * 28]
)
def test_secret_patterns(value):
    assert gate.SECRET.search(value)


def test_release_facts_must_match_github_assets(tmp_path, monkeypatch):
    repo = "example/repo"
    version = "0.1.0.dev1"
    tag = f"v{version}"
    sha = "a" * 40
    tar = f"zhenzhen_seedancevideo_mcp-{version}.tar.gz"
    wheel = f"zhenzhen_seedancevideo_mcp-{version}-py3-none-any.whl"
    (tmp_path / "pyproject.toml").write_text(f'[project]\nversion="{version}"\n')
    (tmp_path / "README.md").write_text(f"{tag} {sha}")
    (tmp_path / "MANUAL.md").write_text(f"{tag} {sha} {'b' * 64}")
    assets = [
        {"name": tar, "digest": "sha256:" + "b" * 64},
        {"name": wheel, "digest": "sha256:" + "c" * 64},
        {
            "name": "SHA256SUMS.txt",
            "digest": "sha256:"
            + hashlib.sha256(f"{'b' * 64}  {tar}\n{'c' * 64}  {wheel}\n".encode()).hexdigest(),
        },
    ]

    def api(endpoint):
        if "/releases/tags/" in endpoint:
            return {"draft": False, "tag_name": tag, "assets": assets}
        return {"object": {"type": "commit", "sha": sha}}

    def run(args, **kwargs):
        if args[0] == "gh":
            Path(args[args.index("--dir") + 1], "SHA256SUMS.txt").write_bytes(
                f"{'b' * 64}  {tar}\n{'c' * 64}  {wheel}\n".encode()
            )
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(gate, "gh_json", api)
    monkeypatch.setattr(gate.subprocess, "run", run)
    monkeypatch.setattr(gate, "git", lambda *args: "README.md\n")
    assert gate.verify_release(repo, tmp_path, "base", "head")
    assets[0]["digest"] = "sha256:" + "d" * 64
    assert not gate.verify_release(repo, tmp_path, "base", "head")


def test_gate_falls_back_when_evidence_unavailable(tmp_path, monkeypatch):
    output, summary = tmp_path / "output", tmp_path / "summary"
    monkeypatch.setenv("BASE_SHA", "a" * 40)
    monkeypatch.setenv("HEAD_SHA", "b" * 40)
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/repo")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setattr(gate, "input_fingerprint", lambda revision: "same")
    monkeypatch.setattr(gate, "git", lambda *args: "README.md\n")
    monkeypatch.setattr(gate, "classify", lambda *args: True)
    monkeypatch.setattr(gate, "local_links", lambda *args: True)
    monkeypatch.setattr(gate, "verify_release", lambda *args: True)
    monkeypatch.setattr(gate, "current_evidence", lambda: {})
    monkeypatch.setattr(gate, "trusted_run", lambda *args: None)
    monkeypatch.setattr(
        gate.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0)
    )
    assert gate.main() == 0
    assert output.read_text().strip() == "reuse=false"
    assert "Evidence unavailable" in summary.read_text()
    monkeypatch.setattr(gate, "verify_release", lambda *args: False)
    assert gate.main() == 1


def test_manual_is_excluded_but_unknown_file_is_not(monkeypatch):
    monkeypatch.setattr(gate, "git", lambda *args: "MANUAL.md\n")
    assert gate.classify("base", "head")
    monkeypatch.setattr(gate, "git", lambda *args: "MANUAL.md\npyproject.toml\n")
    assert not gate.classify("base", "head")


def test_gate_reports_reuse_only_with_verified_run(tmp_path, monkeypatch):
    output, summary = tmp_path / "output", tmp_path / "summary"
    for key, value in {
        "BASE_SHA": "a" * 40,
        "HEAD_SHA": "b" * 40,
        "GITHUB_REPOSITORY": "example/repo",
        "GITHUB_OUTPUT": str(output),
        "GITHUB_STEP_SUMMARY": str(summary),
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(gate, "input_fingerprint", lambda revision: "same")
    monkeypatch.setattr(gate, "git", lambda *args: "README.md\n")
    monkeypatch.setattr(gate, "classify", lambda *args: True)
    monkeypatch.setattr(gate, "local_links", lambda *args: True)
    monkeypatch.setattr(gate, "verify_release", lambda *args: True)
    monkeypatch.setattr(gate, "current_evidence", lambda: {})
    monkeypatch.setattr(gate, "trusted_run", lambda *args: 123)
    monkeypatch.setattr(
        gate.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0)
    )
    assert gate.main() == 0
    assert output.read_text().strip() == "reuse=true"
    assert "trusted run 123" in summary.read_text()
    assert "MANUAL.md content is excluded" in summary.read_text()
    assert "No candidate package is reused" in summary.read_text()


def test_trusted_run_verifies_github_provenance(monkeypatch):
    repo = "example/repo"
    head, source, tree, merge = "a" * 40, "b" * 40, "c" * 40, "d" * 40
    expected = {
        "schema": 1,
        "scope": "full-windows-lint-format-tests-build",
        "operational_inputs_sha256": "e" * 64,
        "excluded_passive_fact_files": sorted(gate.PASSIVE_FACT_FILES),
        "repository": repo,
        "python": "3.12.14",
        "uv": "uv 0.12.9",
        "git": "git version 2.0",
        "gh": "gh version 2.0",
        "runner_os": "Windows",
        "runner_arch": "X64",
        "image_os": "win22",
        "image_version": "image-1",
    }
    evidence = {
        **expected,
        "run_id": "123",
        "run_attempt": "1",
        "event": "pull_request",
        "workflow_ref": f"{repo}/.github/workflows/pr-checks.yml@refs/pull/1/merge",
        "source_commit": source,
        "source_tree": tree,
    }
    run = {
        "id": 123,
        "run_attempt": 1,
        "head_sha": head,
        "status": "completed",
        "conclusion": "success",
        "event": "pull_request",
        "path": ".github/workflows/pr-checks.yml",
        "head_repository": {"full_name": repo},
    }
    full_pull = {
        "merged": True,
        "merge_commit_sha": merge,
        "head": {"sha": head, "repo": {"full_name": repo}},
        "base": {"ref": "dev"},
    }

    def api(endpoint):
        if "/workflows/" in endpoint:
            return {"workflow_runs": [run]}
        if endpoint.endswith("/pulls"):
            return [{"number": 1, "merged_at": "2026-01-01", "merge_commit_sha": merge}]
        if endpoint.endswith("/artifacts"):
            return {"artifacts": [{"name": "windows-candidate-123", "expired": False}]}
        if "/git/commits/" in endpoint:
            return {"tree": {"sha": tree}, "parents": [{"sha": head}]}
        return full_pull

    def run_command(args, **kwargs):
        if args[0] == "gh":
            Path(args[args.index("--dir") + 1], "VERIFICATION_EVIDENCE.json").write_text(
                json.dumps(evidence), encoding="utf-8"
            )
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(gate, "gh_json", api)
    monkeypatch.setattr(gate.subprocess, "run", run_command)
    monkeypatch.setattr(gate, "input_fingerprint", lambda revision: "e" * 64)
    assert gate.trusted_run(repo, "base", expected) == 123
    evidence["image_version"] = "different"
    assert gate.trusted_run(repo, "base", expected) is None


def test_classifier_against_isolated_git_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def git(*args):
        return subprocess.check_output(["git", *args], text=True).strip()

    git("init")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Synthetic Test")
    (tmp_path / "README.md").write_text("current", encoding="utf-8")
    (tmp_path / "MANUAL.md").write_text("manual", encoding="utf-8")
    (tmp_path / "runtime.py").write_text("unchanged", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "base")
    base = git("rev-parse", "HEAD")
    (tmp_path / "MANUAL.md").write_text("human reviewed manual", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "manual")
    assert gate.classify(base, git("rev-parse", "HEAD"))
    (tmp_path / "runtime.py").write_text("changed", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "code")
    assert not gate.classify(base, git("rev-parse", "HEAD"))
