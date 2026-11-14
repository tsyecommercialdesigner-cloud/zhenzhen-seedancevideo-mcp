import subprocess
import sys

import pytest

from zhenzhen_seedance_video import __version__
from zhenzhen_seedance_video.cli import main


def test_version_entrypoint():
    result = subprocess.run(
        [sys.executable, "-m", "zhenzhen_seedance_video", "--version"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == __version__
    assert not result.stderr


@pytest.mark.parametrize("mode", ["stdio", "backend"])
def test_invalid_configuration_does_not_fake_success(mode, capsys):
    assert main([mode]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "CONFIG_INVALID: ZHENZHEN_SEEDANCE_API_KEY" in output.err


def test_wrapped_launch_error_is_bounded_and_actionable(monkeypatch, capsys):
    from zhenzhen_seedance_video.runtime import RuntimeErrorCode

    async def fail():
        raise ExceptionGroup(
            "sensitive wrapper details", [RuntimeErrorCode("BACKEND_LAUNCH_OR_JOB_INCOMPATIBLE")]
        )

    monkeypatch.setattr("zhenzhen_seedance_video.frontend.run_frontend", fail)
    assert main(["stdio"]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err.strip() == "BACKEND_LAUNCH_OR_JOB_INCOMPATIBLE"
