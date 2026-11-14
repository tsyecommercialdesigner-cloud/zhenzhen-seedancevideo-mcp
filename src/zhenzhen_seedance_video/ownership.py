"""Windows stable exclusive handles and process identity checks.

No path deletion, process termination, or database initialization occurs here.
"""

from dataclasses import dataclass
from pathlib import Path

import pywintypes
import win32api
import win32con
import win32event
import win32file
import win32process

from .windows_security import protect_directory, reject_reparse_path


class OwnershipError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    created_at: str


def process_identity(pid):
    if type(pid) is not int or pid <= 0:
        raise OwnershipError("INVALID_PROCESS_IDENTITY")
    try:
        handle = win32api.OpenProcess(0x1000 | win32con.SYNCHRONIZE, False, pid)
    except pywintypes.error:
        raise OwnershipError("PROCESS_IDENTITY_UNAVAILABLE") from None
    try:
        return ProcessIdentity(
            pid, win32process.GetProcessTimes(handle)["CreationTime"].isoformat()
        )
    finally:
        handle.Close()


def confirm_exited(identity: ProcessIdentity):
    if type(identity.pid) is not int or identity.pid <= 0 or not identity.created_at:
        raise OwnershipError("INVALID_PROCESS_IDENTITY")
    try:
        handle = win32api.OpenProcess(0x1000 | win32con.SYNCHRONIZE, False, identity.pid)
    except pywintypes.error as error:
        if error.winerror == 87:  # A previously valid PID no longer exists.
            return
        raise OwnershipError("OLD_PROCESS_EXIT_UNCONFIRMED") from None
    try:
        created = win32process.GetProcessTimes(handle)["CreationTime"].isoformat()
        if created != identity.created_at:
            return  # PID reuse: this is a different process, never terminate it.
        if win32event.WaitForSingleObject(handle, 0) != win32event.WAIT_OBJECT_0:
            raise OwnershipError("OLD_PROCESS_STILL_ALIVE")
    except pywintypes.error:
        raise OwnershipError("OLD_PROCESS_EXIT_UNCONFIRMED") from None
    finally:
        handle.Close()


class StableLock:
    def __init__(self, directory: Path, name: str):
        if name not in ("startup.lock", "owner.lock"):
            raise OwnershipError("INVALID_LOCK_NAME")
        protect_directory(directory)
        self.path = directory / name
        self.handle = None

    def acquire(self):
        if self.handle is not None:
            raise OwnershipError("LOCK_ALREADY_HELD")
        reject_reparse_path(self.path)
        try:
            self.handle = win32file.CreateFile(
                str(self.path),
                win32con.GENERIC_READ | win32con.GENERIC_WRITE,
                0,
                None,
                win32con.OPEN_ALWAYS,
                win32con.FILE_ATTRIBUTE_NORMAL,
                None,
            )
        except pywintypes.error as error:
            code = "LOCK_BUSY" if error.winerror in (32, 33) else "LOCK_UNAVAILABLE"
            raise OwnershipError(code) from None
        return self

    def close(self):
        if self.handle is not None:
            self.handle.Close()
            self.handle = None

    def __enter__(self):
        return self if self.handle is not None else self.acquire()

    def __exit__(self, *args):
        self.close()


def acquire_ownership(directory: Path, previous: ProcessIdentity | None):
    """Must run under the startup lock before opening the shared task database."""
    owner = StableLock(directory, "owner.lock").acquire()
    try:
        if previous is not None:
            confirm_exited(previous)
    except BaseException:
        owner.close()
        raise
    return owner
