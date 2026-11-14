"""Windows file publication: pin ancestors, retain originals, never transcode."""

import asyncio
import hashlib
import os
import struct
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

import pywintypes
import win32con
import win32file

from .materials import MaterialError, locked_source
from .windows_security import reject_reparse_path


class ArtifactError(RuntimeError):
    pass


def destination(value, workspace=None):
    if not isinstance(value, str) or not value or value.startswith(("\\\\", "//")):
        raise ArtifactError("INVALID_TARGET_PATH")
    path = Path(value)
    if path.drive and not path.is_absolute() or ":" in value[len(path.drive) :]:
        raise ArtifactError("INVALID_TARGET_PATH")
    if any(part.endswith((".", " ")) for part in path.parts if part not in (".", "..")):
        raise ArtifactError("INVALID_TARGET_PATH")
    if path.is_reserved():
        raise ArtifactError("INVALID_TARGET_PATH")
    if not path.is_absolute():
        if workspace is None:
            raise ArtifactError("WORKSPACE_REQUIRED")
        base = destination(workspace)
        path = Path(os.path.abspath(base / path))
        if not path.is_relative_to(base):
            raise ArtifactError("TARGET_OUTSIDE_WORKSPACE")
    else:
        path = Path(os.path.abspath(path))
    reject_reparse_path(path)
    return path


@contextmanager
def pinned_directory(path):
    """Hold every ancestor against rename/delete while traversing and publishing."""
    handles = []
    try:
        for part in reversed((path, *path.parents)):
            reject_reparse_path(part)
            part.mkdir(exist_ok=True)
            handle = win32file.CreateFile(
                str(part),
                win32con.GENERIC_READ,
                win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
                None,
                win32con.OPEN_EXISTING,
                win32con.FILE_FLAG_BACKUP_SEMANTICS | win32file.FILE_FLAG_OPEN_REPARSE_POINT,
                None,
            )
            handles.append(handle)
            reject_reparse_path(part)
        yield
    finally:
        for handle in reversed(handles):
            handle.Close()


def fingerprint(path):
    with locked_source(str(path)) as (stream, info):
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
        return {
            "sha256": digest,
            "size_bytes": info.st_size,
            "device": info.st_dev,
            "inode": info.st_ino,
        }


def container(path):
    """Structural ISO BMFF/JPEG check; not a playback or full image decoder."""
    with locked_source(str(path)) as (stream, info):
        if stream.read(2) == b"\xff\xd8":
            return _jpeg_container(stream, info.st_size)
        stream.seek(0)
        offset, kinds, brand = 0, set(), None
        while offset < info.st_size:
            head = stream.read(8)
            if len(head) != 8:
                raise ArtifactError("INVALID_VIDEO_CONTAINER")
            size, kind = struct.unpack(">I4s", head)
            header = 8
            if size == 1:
                extra = stream.read(8)
                if len(extra) != 8:
                    raise ArtifactError("INVALID_VIDEO_CONTAINER")
                size, header = struct.unpack(">Q", extra)[0], 16
            elif size == 0:
                size = info.st_size - offset
            if size < header or offset + size > info.st_size:
                raise ArtifactError("INVALID_VIDEO_CONTAINER")
            if kind == b"ftyp":
                if size < header + 8:
                    raise ArtifactError("INVALID_VIDEO_CONTAINER")
                brand = stream.read(4)
            if kind in (b"moov", b"mdat") and size <= header:
                raise ArtifactError("INVALID_VIDEO_CONTAINER")
            kinds.add(kind)
            offset += size
            stream.seek(offset)
        if not {b"ftyp", b"moov", b"mdat"} <= kinds:
            raise ArtifactError("INVALID_VIDEO_CONTAINER")
        if brand == b"qt  ":
            return "mov"
        if brand in {b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"M4V ", b"dash"}:
            return "mp4"
        raise ArtifactError("UNSUPPORTED_VIDEO_CONTAINER")


def _jpeg_container(stream, size):
    saw_frame = False
    for _ in range(4096):
        if stream.read(1) != b"\xff":
            break
        marker = stream.read(1)
        while marker == b"\xff":
            marker = stream.read(1)
        length = stream.read(2)
        if len(length) != 2:
            break
        length = int.from_bytes(length, "big")
        if length < 2 or stream.tell() + length - 2 > size:
            break
        payload = stream.read(length - 2)
        if marker in (b"\xc0", b"\xc1", b"\xc2"):
            if (
                len(payload) < 6
                or not int.from_bytes(payload[1:3], "big")
                or not int.from_bytes(payload[3:5], "big")
            ):
                break
            components = payload[5]
            if not components or len(payload) != 6 + 3 * components:
                break
            saw_frame = True
        if marker == b"\xda":
            if not saw_frame or len(payload) < 4 or len(payload) != 4 + 2 * payload[0]:
                break
            if stream.tell() >= size - 2:
                break
            stream.seek(-2, os.SEEK_END)
            if stream.read(2) == b"\xff\xd9":
                return "jpg"
            break
    raise ArtifactError("INVALID_IMAGE_CONTAINER")


def copy_file(source, target, expected, *, overwrite=False, stop=None, hook=lambda point: None):
    temporary = target.parent / (".seedance-copy-" + uuid.uuid4().hex + ".tmp")
    created = False
    try:
        with pinned_directory(source.parent), pinned_directory(target.parent):
            reject_reparse_path(target)
            if target.exists() and os.path.samefile(source, target):
                return {"path": str(source), "copied": False, "reason": "SOURCE_EQUALS_TARGET"}
            if target.exists() and not overwrite:
                raise ArtifactError("TARGET_EXISTS")
            with locked_source(str(source)) as (input_file, _):
                digest, size = hashlib.sha256(), 0
                with temporary.open("xb") as output:
                    created = True
                    while block := input_file.read(1024 * 1024):
                        if stop and stop.is_set():
                            raise ArtifactError("COPY_CANCELLED")
                        output.write(block)
                        digest.update(block)
                        size += len(block)
                    output.flush()
                    os.fsync(output.fileno())
                if digest.hexdigest() != expected["sha256"] or size != expected["size_bytes"]:
                    raise ArtifactError("ARTIFACT_CHANGED")
                if fingerprint(temporary)["sha256"] != expected["sha256"]:
                    raise ArtifactError("COPY_INTEGRITY_FAILED")
                hook("copy_before_publish")
                if stop and stop.is_set():
                    raise ArtifactError("COPY_CANCELLED")
                reject_reparse_path(target)
                (os.replace if overwrite else os.rename)(temporary, target)
                created = False
                hook("copy_after_publish")
                return {"path": str(target), "copied": True, "size_bytes": size}
    except (OSError, pywintypes.error, MaterialError):
        raise ArtifactError("COPY_STORAGE_OR_TARGET_CONFLICT") from None
    finally:
        if created:
            temporary.unlink(missing_ok=True)


async def copy_async(source, target, expected, *, overwrite=False, hook=lambda point: None):
    stop = threading.Event()
    work = asyncio.create_task(
        asyncio.to_thread(
            copy_file, source, target, expected, overwrite=overwrite, stop=stop, hook=hook
        )
    )
    try:
        return await asyncio.shield(work)
    except asyncio.CancelledError:
        stop.set()
        await asyncio.gather(work, return_exceptions=True)
        raise
