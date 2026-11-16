"""Exercise the real workflow precheck against isolated Git histories."""

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/pr-checks.yml"


@pytest.fixture
def release_repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def git(*args):
        return subprocess.check_output(["git", *args], text=True, encoding="utf-8").strip()

    git("init", "-b", "main")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Synthetic Test")
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.1.0.dev1"\n')
    (tmp_path / "MANUAL.md").write_text("original\n")
    (tmp_path / "runtime.py").write_text("runtime\n")
    git("add", ".")
    git("commit", "-m", "base")
    git("switch", "-c", "dev")
    (tmp_path / "runtime.py").write_text("released runtime\n")
    git("add", ".")
    git("commit", "-m", "release source")
    source = git("rev-parse", "HEAD")
    git("switch", "main")
    git("merge", "--no-ff", "dev", "-m", "release")
    release = git("rev-parse", "HEAD")
    git("tag", "v0.1.0.dev1")
    git("update-ref", "refs/remotes/origin/main", release)
    git("switch", "dev")
    git("switch", "-c", "manual-backfill")
    (tmp_path / "MANUAL.md").write_text("human reviewed release facts\n")
    git("add", ".")
    git("commit", "-m", "manual")
    return git, source, release


def precheck(tmp_path, base, head):
    workflow = WORKFLOW.read_text(encoding="utf-8-sig")
    section = workflow.split("      - name: Identify manual-only published backfill\n", 1)[1]
    section = section.split("      - uses: astral-sh/setup-uv@", 1)[0]
    script = textwrap.dedent(section.split("        run: |\n", 1)[1])
    output, summary = tmp_path / "gate-output", tmp_path / "gate-summary"
    output.unlink(missing_ok=True)
    summary.unlink(missing_ok=True)
    env = dict(
        os.environ,
        BASE_SHA=base,
        HEAD_SHA=head,
        GITHUB_OUTPUT=str(output),
        GITHUB_STEP_SUMMARY=str(summary),
    )
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-Command", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return output.read_text(encoding="utf-8-sig").strip(), (
        summary.read_text(encoding="utf-8-sig") if summary.exists() else ""
    )


def test_published_merge_source_manual_only_is_lightweight(release_repo, tmp_path):
    git, base, release = release_repo
    assert subprocess.run(["git", "merge-base", "--is-ancestor", release, "HEAD"]).returncode == 1
    output, summary = precheck(tmp_path, base, git("rev-parse", "HEAD"))
    assert output == "manual_only=true"
    assert "no tests, build, Release API validation or artifact reuse" in summary
    assert "not full release acceptance" in summary


def test_other_changes_and_unknown_release_fall_back(release_repo, tmp_path):
    git, base, _ = release_repo
    (tmp_path / "runtime.py").write_text("modified\n")
    git("add", "runtime.py")
    git("commit", "-m", "code change")
    assert precheck(tmp_path, base, git("rev-parse", "HEAD"))[0] == "manual_only=false"
    git("reset", "--hard", "HEAD^")
    git("tag", "-d", "v0.1.0.dev1")
    assert precheck(tmp_path, base, git("rev-parse", "HEAD"))[0] == "manual_only=false"


def test_release_relation_accepts_source_and_rejects_unrelated(release_repo, tmp_path):
    import importlib.util
    import sys

    scripts = str(WORKFLOW.parents[2] / "scripts")
    sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        "ci_backfill_relation", Path(scripts) / "ci_backfill.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    git, _, release = release_repo
    assert module.release_source_reachable(release)
    git("switch", "--orphan", "unrelated")
    (tmp_path / "orphan.txt").write_text("unrelated")
    git("add", "orphan.txt")
    git("commit", "-m", "unrelated")
    assert not module.release_source_reachable(release)
