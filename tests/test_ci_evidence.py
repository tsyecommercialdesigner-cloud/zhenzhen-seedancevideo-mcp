"""Evidence input fingerprint excludes only the reviewed passive fact files."""

import importlib.util
import subprocess
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "ci_evidence", Path(__file__).resolve().parents[1] / "scripts" / "ci_evidence.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
input_fingerprint = module.input_fingerprint


def test_fingerprint_detects_operational_changes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def git(*args):
        subprocess.run(["git", *args], check=True, capture_output=True)

    git("init")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Synthetic Test")
    (tmp_path / "README.md").write_text("release one", encoding="utf-8")
    (tmp_path / "runtime.py").write_text("version = 1", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "base")
    original = input_fingerprint("HEAD")
    (tmp_path / "README.md").write_text("release two", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "passive")
    assert input_fingerprint("HEAD") == original
    (tmp_path / "runtime.py").write_text("version = 2", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "operational")
    assert input_fingerprint("HEAD") != original
