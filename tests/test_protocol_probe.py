"""Exercise the installed local protocol probe without provider access."""

import asyncio
import os
import subprocess
import sys

import pytest


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


def test_probe_isolates_provider_mode(tmp_path):
    installation = tmp_path / "installation" / ".env"
    original = (
        "ZHENZHEN_SEEDANCE_API_KEY=private-placeholder\nZHENZHEN_SEEDANCE_EXECUTION_MODE=provider\n"
    )
    installation.write_text(original, encoding="utf-8")
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
    assert result.returncode == 0, result.stderr
    assert "local=ok" in result.stdout
    assert not list(tmp_path.glob("seedance-probe-*"))
    assert installation.read_text(encoding="utf-8") == original
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


@pytest.mark.asyncio
async def test_probe_does_not_connect_existing_backend_or_modify_task_database(
    monkeypatch, tmp_path
):
    from zhenzhen_seedance_video.admission import AdmissionService
    from zhenzhen_seedance_video.config import installation_root, load_configuration
    from zhenzhen_seedance_video.rpc import RPCServer
    from zhenzhen_seedance_video.storage import Database

    monkeypatch.setenv("ZHENZHEN_SEEDANCE_API_KEY", "sentinel-placeholder")
    config = load_configuration()
    db = Database(config.state_dir)
    admission = AdmissionService(db, config, "sentinel-binding")
    server = RPCServer(config, {})
    connections = []
    original_accept = server._accept

    async def observed_accept(reader, writer):
        connections.append(True)
        await original_accept(reader, writer)

    server._accept = observed_accept
    try:
        await db.execute(lambda c: c.execute("CREATE TABLE probe_sentinel (value TEXT)"))
        await db.execute(lambda c: c.execute("INSERT INTO probe_sentinel VALUES ('unchanged')"))
        accepted = await admission.submit(
            "sentinel-request", {"model": "seedance-2.0-mini-t2v", "prompt": "sentinel"}
        )

        def snapshot(c):
            task = c.execute(
                "SELECT * FROM tasks WHERE task_id=?", (accepted["task_id"],)
            ).fetchone()
            events = c.execute("SELECT * FROM task_events ORDER BY event_id").fetchall()
            return dict(task), [tuple(row) for row in events]

        before_tasks = await db.execute(snapshot, write=False)
        await server.start()
        server.publish_discovery(config.root / "runtime")
        discovery = (config.root / "runtime/discovery.json").read_bytes()
        install_env = installation_root() / ".env"
        install_env.write_text(
            "ZHENZHEN_SEEDANCE_API_KEY=sentinel-placeholder\n"
            "ZHENZHEN_SEEDANCE_EXECUTION_MODE=provider\n",
            encoding="utf-8",
        )
        before = install_env.read_bytes()
        environment = dict(os.environ, TEMP=str(tmp_path), TMP=str(tmp_path))
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-m", "zhenzhen_seedance_video.protocol_probe"],
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "local=ok" in result.stdout
        assert not connections
        assert (config.root / "runtime/discovery.json").read_bytes() == discovery
        assert install_env.read_bytes() == before
        assert await db.execute(snapshot, write=False) == before_tasks
        assert (
            await db.execute(
                lambda c: c.execute("SELECT value FROM probe_sentinel").fetchone()[0], write=False
            )
            == "unchanged"
        )
    finally:
        await server.close()
        await admission.close()
        await db.close()
