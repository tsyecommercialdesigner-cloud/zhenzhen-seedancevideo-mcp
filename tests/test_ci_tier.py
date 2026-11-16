"""Run the actual test-only workflow step against a disposable Git repository."""

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/pr-checks.yml"


@pytest.mark.parametrize("extra_change", [False, True])
def test_test_only_gate_runs_changed_tests_or_falls_back(tmp_path, extra_change):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path, text=True).strip()

    git("init", "-b", "dev")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Synthetic Test")
    (tmp_path / "tests").mkdir()
    test = tmp_path / "tests/test_example.py"
    test.write_text("def test_old(): pass\n", encoding="utf-8")
    (tmp_path / "runtime.py").write_text("old\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "base")
    base = git("rev-parse", "HEAD")
    test.write_text("def test_new(): pass\n", encoding="utf-8")
    if extra_change:
        (tmp_path / "runtime.py").write_text("new\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "change")
    workflow = WORKFLOW.read_text(encoding="utf-8-sig")
    section = workflow.split("      - name: Check isolated test-only development changes\n", 1)[1]
    section = section.split("      - name: Classify and verify trusted evidence\n", 1)[0]
    body = textwrap.dedent(section.split("        run: |\n", 1)[1])
    script = (
        "function uv { $args -join ' ' | Add-Content -LiteralPath $env:UV_CALLS; "
        "$global:LASTEXITCODE=0 }\n" + body
    )
    output, summary, calls = tmp_path / "output", tmp_path / "summary", tmp_path / "calls"
    env = dict(
        os.environ,
        BASE_SHA=base,
        BASE_REF="dev",
        GITHUB_OUTPUT=str(output),
        GITHUB_STEP_SUMMARY=str(summary),
        RUNNER_TEMP=str(tmp_path),
        UV_CALLS=str(calls),
    )
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-Command", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (
        output.read_text(encoding="utf-8-sig").strip()
        == f"tests_only={str(not extra_change).lower()}"
    )
    if extra_change:
        assert not calls.exists()
    else:
        assert "tests/test_example.py" in calls.read_text(encoding="utf-8-sig")
        assert "no build or complete test suite" in summary.read_text(encoding="utf-8-sig")
