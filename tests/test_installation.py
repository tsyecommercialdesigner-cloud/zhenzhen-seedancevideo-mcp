import asyncio
import json
import os
import shutil
import sqlite3
import subprocess
import tarfile
import zipfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from test_lifecycle import factory as factory
from test_runtime import wait_exit
from test_scheduler import submit

from zhenzhen_seedance_video.admission import AdmissionService
from zhenzhen_seedance_video.ownership import ProcessIdentity
from zhenzhen_seedance_video.scheduler import Scheduler
from zhenzhen_seedance_video.storage import Database

REPO = Path(__file__).resolve().parents[1]


async def command(args, **kwargs):
    result = await asyncio.to_thread(
        subprocess.run,
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        **kwargs,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


async def test_clean_source_install_stdio_discovery_and_external_state(tmp_path):
    packages = tmp_path / "packages"
    await command(["uv", "build", "--out-dir", str(packages)], cwd=REPO)
    wheel = next(packages.glob("*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        assert all(
            n.startswith(
                ("zhenzhen_seedance_video/", "zhenzhen_seedancevideo_mcp-0.1.0.dev0.dist-info/")
            )
            for n in archive.namelist()
        )
        assert not any("synthetic" in n or "tests/" in n for n in archive.namelist())
    install = tmp_path / "install"
    install.mkdir()
    with tarfile.open(next(packages.glob("*.tar.gz"))) as archive:
        names = archive.getnames()
        assert not any("/tests/" in n or "/.cache/" in n or n.endswith("/.env") for n in names)
        assert any(n.endswith("/uv.lock") for n in names)
        assert any(n.endswith("/.env.example") for n in names)
        archive.extractall(install, filter="data")
    project = next(install.iterdir())
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    for key in tuple(environment):
        if key.startswith("ZHENZHEN_SEEDANCE_"):
            environment.pop(key)
    environment["UV_NO_PROGRESS"] = "1"
    await command(
        ["uv", "--directory", str(project), "sync", "--frozen", "--no-dev", "--offline"],
        env=environment,
    )
    version = await command(
        [
            "uv",
            "--directory",
            str(project),
            "run",
            "--no-sync",
            "zhenzhen-seedance-video",
            "--version",
        ],
        env=environment,
    )
    assert version.strip() == "0.1.0.dev0"
    python = project / ".venv/Scripts/python.exe"
    location = await command(
        [
            str(python),
            "-c",
            "import zhenzhen_seedance_video; print(zhenzhen_seedance_video.__file__)",
        ],
        env=environment,
        cwd=tmp_path,
    )
    assert str(project) in location and str(REPO / "src") not in location
    # Do not replace installation_root: verify the installed project locates its own .env.
    bootstrap = tmp_path / "installed-bootstrap"
    bootstrap.mkdir()
    (bootstrap / "sitecustomize.py").write_text(
        "from zhenzhen_seedance_video import config\n"
        "config._read_user_environment=lambda excluded: {}\n",
        encoding="utf-8",
    )
    environment["PYTHONPATH"] = str(bootstrap)
    environment["ZHENZHEN_SEEDANCE_API_KEY"] = "wrong-process-value"
    (project / ".env").write_text(
        "ZHENZHEN_SEEDANCE_API_KEY=synthetic-file-key\nZHENZHEN_SEEDANCE_SHUTDOWN_GRACE_SECONDS=1\nZHENZHEN_SEEDANCE_SHUTDOWN_DRAIN_SECONDS=1\n",
        encoding="utf-8",
    )
    root = tmp_path / "local-app-data/ZhenzhenSeedanceVideo"
    params = StdioServerParameters(
        command=str(python), args=["-m", "zhenzhen_seedance_video", "stdio"], env=environment
    )
    async with stdio_client(params) as streams:
        async with ClientSession(*streams, read_timeout_seconds=10) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            assert "submit_video" in {tool.name for tool in tools}
            assert not (await session.list_resources()).resources
            assert not (await session.list_prompts()).prompts
            result = await session.call_tool(
                "submit_video",
                {
                    "request_key": "installed",
                    "request": {"model": "seedance-2.0-mini-t2v", "prompt": "synthetic"},
                },
            )
            assert result.structured_content["accepted"]
            record = json.loads((root / "runtime/discovery.json").read_text())
    await wait_exit(ProcessIdentity(record["pid"], record["created_at"]))
    database = root / "state/tasks.sqlite3"
    before = database.read_bytes()
    output = root / "outputs/retention-canary.mp4"
    output.parent.mkdir(exist_ok=True)
    output.write_bytes(b"synthetic retained output")
    # Rehearse installation switching without claiming an untested schema/version upgrade.
    candidate_root = tmp_path / "candidate-install"
    candidate_root.mkdir()
    with tarfile.open(next(packages.glob("*.tar.gz"))) as archive:
        archive.extractall(candidate_root, filter="data")
    candidate = next(candidate_root.iterdir())
    await command(
        ["uv", "--directory", str(candidate), "sync", "--frozen", "--no-dev", "--offline"],
        env=environment,
    )
    await asyncio.to_thread(shutil.copyfile, project / ".env", candidate / ".env")
    expected_env = (project / ".env").read_bytes()

    async def verify_existing(installed_project):
        installed_python = installed_project / ".venv/Scripts/python.exe"
        installed_location = await command(
            [
                str(installed_python),
                "-c",
                "import zhenzhen_seedance_video; print(zhenzhen_seedance_video.__file__)",
            ],
            env=environment,
            cwd=tmp_path,
        )
        assert str(installed_project) in installed_location
        client = StdioServerParameters(
            command=str(installed_python),
            args=["-m", "zhenzhen_seedance_video", "stdio"],
            env=environment,
        )
        async with stdio_client(client) as streams:
            async with ClientSession(*streams, read_timeout_seconds=10) as session:
                await session.initialize()
                found = await session.call_tool(
                    "find_task_by_request_key", {"request_key": "installed"}
                )
                assert found.structured_content["task_id"] == result.structured_content["task_id"]
                assert found.structured_content["version"] == result.structured_content["version"]
                assert found.structured_content["stale"] is False
                discovery = json.loads((root / "runtime/discovery.json").read_text())
        await wait_exit(ProcessIdentity(discovery["pid"], discovery["created_at"]))
        assert (installed_project / ".env").read_bytes() == expected_env
        assert output.read_bytes() == b"synthetic retained output"
        with sqlite3.connect(database) as connection:
            assert connection.execute("SELECT count(*) FROM tasks").fetchone()[0] == 1
            assert connection.execute("SELECT count(*) FROM attempts").fetchone()[0] == 0
        return discovery["instance_id"]

    upgraded = await verify_existing(candidate)
    rolled_back = await verify_existing(project)
    assert upgraded != rolled_back != record["instance_id"]
    assert candidate.resolve().is_relative_to(tmp_path.resolve())
    await asyncio.to_thread(shutil.rmtree, candidate)
    # Byte identity is checked after the final clean shutdown; SQLite startup may checkpoint.
    before = database.read_bytes()
    # Only this newly extracted installation may be removed.
    assert project.resolve().is_relative_to(tmp_path.resolve())
    await asyncio.to_thread(shutil.rmtree, project)
    assert database.read_bytes() == before and output.read_bytes() == b"synthetic retained output"


async def test_backup_window_is_quarantined_before_any_restore_dispatch(factory, tmp_path):
    open_services, adapter, _, _ = factory
    async with open_services() as original:
        await original.recover()
        task = await submit(original.admission, "backup-window")
        path = original.db.path
        config = original.config
    backup = tmp_path / "backup-state"
    backup.mkdir()
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as source:
        with sqlite3.connect(backup / "tasks.sqlite3") as target:
            source.backup(target)
            assert target.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            # Documented offline review barrier for every unfinished backup task.
            target.execute(
                """UPDATE tasks SET auto_mode='needs_attention',
                attention=json_insert(attention,'$[#]','BACKUP_RESTORE_REVIEW_REQUIRED'),
                version=version+1
                WHERE remote_state NOT IN ('succeeded','failed','cancelled')
                AND locally_cancelled=0 AND auto_mode!='abandoned'"""
            )
    async with open_services() as live:
        await live.recover()
        await live.scheduler.dispatch()
        assert adapter.posts == [task["task_id"]]
    restored = Database(backup)
    admission = AdmissionService(restored, config, "binding")
    engine = Scheduler(restored, config, "binding", adapter, leases=live.leases)
    try:
        await engine.recover()
        assert await engine.dispatch() == []
        assert adapter.posts == [task["task_id"]]
        assert (await engine.state.get(task["task_id"]))["auto_mode"] == "needs_attention"
    finally:
        await engine.close()
        await admission.close()
        await restored.close()
