import concurrent.futures
import os
import subprocess
import sys

import pytest
import pywintypes

from zhenzhen_seedance_video.ownership import (
    OwnershipError,
    ProcessIdentity,
    StableLock,
    acquire_ownership,
    confirm_exited,
    process_identity,
)


def test_live_process_never_taken_over_and_handle_released(tmp_path):
    identity = process_identity(os.getpid())
    with pytest.raises(OwnershipError, match="STILL_ALIVE"):
        acquire_ownership(tmp_path, identity)
    with StableLock(tmp_path, "owner.lock"):
        with pytest.raises(OwnershipError, match="LOCK_BUSY"):
            StableLock(tmp_path, "owner.lock").acquire()
    assert (tmp_path / "owner.lock").exists()


def test_pid_reuse_is_not_the_old_process():
    identity = ProcessIdentity(os.getpid(), "old-creation-time")
    confirm_exited(identity)


def test_access_denied_does_not_confirm_exit(monkeypatch):
    def denied(*args):
        raise pywintypes.error(5, "OpenProcess", "synthetic denied")

    monkeypatch.setattr("zhenzhen_seedance_video.ownership.win32api.OpenProcess", denied)
    with pytest.raises(OwnershipError, match="EXIT_UNCONFIRMED"):
        confirm_exited(ProcessIdentity(123, "old"))


def test_four_real_processes_get_only_one_owner(tmp_path):
    script = """
import sys
from pathlib import Path
from zhenzhen_seedance_video.ownership import StableLock, OwnershipError
lock = StableLock(Path(sys.argv[1]), 'owner.lock')
try:
    lock.acquire()
except OwnershipError:
    print('busy', flush=True)
else:
    print('owner', flush=True)
    sys.stdin.readline()
    lock.close()
"""
    processes = []
    try:
        for _ in range(4):
            processes.append(
                subprocess.Popen(
                    [sys.executable, "-c", script, str(tmp_path)],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            )
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(p.stdout.readline) for p in processes]
            outcomes = [future.result(timeout=10).strip() for future in futures]
        assert outcomes.count("owner") == 1
        assert outcomes.count("busy") == 3
        owner_process = processes[outcomes.index("owner")]
        identity = process_identity(owner_process.pid)
        with pytest.raises(OwnershipError, match="LOCK_BUSY"):
            acquire_ownership(tmp_path, identity)
        owner_process.communicate("\n", timeout=10)
        confirm_exited(identity)
        with acquire_ownership(tmp_path, identity):
            pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.communicate("\n", timeout=10)
            else:
                process.communicate(timeout=10)
        assert all(process.returncode == 0 for process in processes)
