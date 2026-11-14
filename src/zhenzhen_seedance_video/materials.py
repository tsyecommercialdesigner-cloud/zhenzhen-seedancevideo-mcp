"""Bounded local intake. No URL fetching, media conversion or upstream upload."""

import hashlib
import msvcrt
import os
import re
import stat
from contextlib import contextmanager
from pathlib import Path

import pywintypes
import win32con
import win32file

from .windows_security import reject_reparse_path


class MaterialError(RuntimeError):
    pass


def local_path(value):
    if not isinstance(value, str):
        raise MaterialError("LOCAL_ABSOLUTE_PATH_REQUIRED")
    path = Path(value)
    if (
        not path.is_absolute()
        or value.startswith(("\\\\", "//"))
        or ":" in value[2:]
        or ".." in path.parts
    ):
        raise MaterialError("LOCAL_ABSOLUTE_PATH_REQUIRED")
    reject_reparse_path(path)
    return path


@contextmanager
def locked_source(value):
    path = local_path(value)
    try:
        handle = win32file.CreateFile(
            str(path),
            win32con.GENERIC_READ,
            win32con.FILE_SHARE_READ,
            None,
            win32con.OPEN_EXISTING,
            win32file.FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        fd = msvcrt.open_osfhandle(handle.Detach(), os.O_RDONLY | os.O_BINARY)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise MaterialError("MATERIAL_NOT_REGULAR")
            yield stream, before
            after = os.fstat(stream.fileno())
            current = path.stat()

            def identity(s):
                return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)

            if identity(before) != identity(after) or identity(before) != identity(current):
                raise MaterialError("MATERIAL_CHANGED")
    except (OSError, pywintypes.error):
        raise MaterialError("MATERIAL_UNAVAILABLE_OR_BUSY") from None


def owned_path(root, name):
    if not isinstance(name, str) or not re.fullmatch(r"[0-9a-f]{32}\.input", name):
        raise MaterialError("MATERIAL_OWNERSHIP_INVALID")
    path = root / name
    reject_reparse_path(path)
    return path


def receive(source, *, limit, destination=None, stop=None):
    """Destination must be a previously reserved service-owned filename."""
    digest = hashlib.sha256()
    size = 0
    created = False
    try:
        with locked_source(source) as (stream, before):
            if before.st_size > limit:
                raise MaterialError("INPUT_BYTES_LIMIT")
            output = None
            try:
                if destination is not None:
                    reject_reparse_path(destination)
                    output = destination.open("xb")
                    created = True
                while block := stream.read(1024 * 1024):
                    if stop is not None and stop.is_set():
                        raise MaterialError("ADMISSION_STOPPED")
                    size += len(block)
                    if size > limit:
                        raise MaterialError("INPUT_BYTES_LIMIT")
                    digest.update(block)
                    if output:
                        output.write(block)
                if output:
                    output.flush()
                    os.fsync(output.fileno())
            finally:
                if output:
                    output.close()
        return {"sha256": digest.hexdigest(), "size_bytes": size}
    except BaseException:
        if created:
            reject_reparse_path(destination)
            destination.unlink(missing_ok=True)
        raise
