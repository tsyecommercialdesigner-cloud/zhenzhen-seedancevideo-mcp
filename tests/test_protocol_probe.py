"""Exercise the installed local protocol probe without provider access."""

import os
import subprocess
import sys


def test_probe_local_mode(tmp_path):
    environment = dict(os.environ)
    environment.update(
        ZHENZHEN_SEEDANCE_API_KEY="synthetic-only",
        ZHENZHEN_SEEDANCE_EXECUTION_MODE="local",
        ZHENZHEN_SEEDANCE_SHUTDOWN_GRACE_SECONDS="1",
        ZHENZHEN_SEEDANCE_SHUTDOWN_DRAIN_SECONDS="1",
        TEMP=str(tmp_path),
        TMP=str(tmp_path),
    )
    result = subprocess.run(
        [sys.executable, "-m", "zhenzhen_seedance_video.protocol_probe"],
        env=environment,
        text=True,
        capture_output=True,
        timeout=40,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "local=ok" in result.stdout
    assert "resources=0 templates=0 prompts=0" in result.stdout
    assert not list(tmp_path.glob("seedance-probe-*"))


def test_probe_rejects_provider_mode(tmp_path):
    environment = dict(os.environ)
    environment.update(
        ZHENZHEN_SEEDANCE_API_KEY="synthetic-only",
        ZHENZHEN_SEEDANCE_EXECUTION_MODE="provider",
        TEMP=str(tmp_path),
        TMP=str(tmp_path),
    )
    result = subprocess.run(
        [sys.executable, "-m", "zhenzhen_seedance_video.protocol_probe"],
        env=environment,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 1
    assert "PROBE_FAILED" in result.stderr
    assert "synthetic-only" not in result.stderr


def test_cleanup_failure_does_not_report_success(monkeypatch, tmp_path, capsys):
    from zhenzhen_seedance_video import protocol_probe

    async def successful_probe(root):
        return "local=ok"

    def fail_cleanup(root):
        raise PermissionError("sensitive diagnostic")

    monkeypatch.setattr(protocol_probe.tempfile, "mkdtemp", lambda **kwargs: str(tmp_path))
    monkeypatch.setattr(protocol_probe, "_probe", successful_probe)
    monkeypatch.setattr(protocol_probe.shutil, "rmtree", fail_cleanup)
    assert protocol_probe.main() == 1
    output = capsys.readouterr()
    assert "local=ok" not in output.out
    assert "PermissionError" in output.err
    assert "sensitive diagnostic" not in output.err
