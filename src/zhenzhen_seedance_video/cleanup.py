"""Durable, bounded cleanup of registered managed copies, never arbitrary files."""

import asyncio
import ctypes
import hashlib
import json
import time
from ctypes import wintypes
from datetime import UTC, datetime

import pywintypes
import win32con
import win32file

from .artifact_files import pinned_directory
from .cleanup_rules import cleanup_reason, enqueue_cleanup
from .material_readers import material_readers
from .materials import owned_path
from .storage import StorageError
from .task_state import _change, _load, _public, _version


def timestamp(value):
    return datetime.fromtimestamp(value, UTC).isoformat()


def delete_copy(root, material):
    target = owned_path(root, material["material_id"] + ".input")
    if str(target) != material["managed_path"]:
        raise RuntimeError("CLEANUP_OWNERSHIP_INVALID")
    with pinned_directory(root):
        try:
            handle = win32file.CreateFile(
                str(target),
                win32con.GENERIC_READ | win32con.DELETE,
                0,
                None,
                win32con.OPEN_EXISTING,
                win32file.FILE_FLAG_OPEN_REPARSE_POINT,
                None,
            )
        except pywintypes.error as error:
            if error.winerror in (2, 3):
                return
            raise RuntimeError("CLEANUP_FILE_BUSY_OR_DENIED") from None
        try:
            attributes = win32file.GetFileInformationByHandle(handle)[0]
            if attributes & (
                win32con.FILE_ATTRIBUTE_REPARSE_POINT | win32con.FILE_ATTRIBUTE_DIRECTORY
            ):
                raise RuntimeError("CLEANUP_UNSAFE_FILE")
            digest, size = hashlib.sha256(), 0
            while True:
                _, chunk = win32file.ReadFile(handle, 1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
            if digest.hexdigest() != material["sha256"] or size != material["size_bytes"]:
                raise RuntimeError("CLEANUP_CONTENT_CHANGED")
            # FileDispositionInfo marks exactly this exclusive handle for deletion.
            api = ctypes.WinDLL("kernel32", use_last_error=True).SetFileInformationByHandle
            api.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
            api.restype = wintypes.BOOL
            delete = wintypes.BOOL(True)
            if not api(int(handle), 4, ctypes.byref(delete), ctypes.sizeof(delete)):
                raise RuntimeError("CLEANUP_DELETE_FAILED")
        finally:
            handle.Close()


class CleanupService:
    def __init__(self, database, configuration, *, wall=time.time, hook=lambda point: None):
        self.db, self.config, self.wall, self.hook = database, configuration, wall, hook
        self.root = configuration.root / "materials"
        self.readers = material_readers(database)
        self.slots = asyncio.Semaphore(configuration.limits["CLEANUP_CONCURRENCY"])
        self.lock = asyncio.Lock()
        self.closed = False
        self.work = set()

    async def scan(self):
        def collect(c):
            for raw in c.execute("SELECT * FROM tasks").fetchall():
                row = dict(raw)
                if cleanup_reason(row):
                    enqueue_cleanup(c, row)
                    self._summary(c, row["task_id"])

        await self.db.execute(collect)

    def _summary(self, c, task_id):
        jobs = c.execute(
            "SELECT j.state FROM cleanup_jobs j JOIN material_copies m USING(material_id) "
            "WHERE m.task_id=?",
            (task_id,),
        ).fetchall()
        state = (
            "failed"
            if any(j[0] == "failed" for j in jobs)
            else "done"
            if all(j[0] == "done" for j in jobs)
            else "pending"
        )
        row = _load(c, task_id)
        reasons = set(json.loads(row["attention"])) - {"MATERIAL_CLEANUP_FAILED"}
        if state == "failed":
            reasons.add("MATERIAL_CLEANUP_FAILED")
        _change(
            c,
            row,
            {"cleanup_state": state, "attention": json.dumps(sorted(reasons))},
            kind="material_cleanup",
            now=timestamp(self.wall()),
        )

    async def due(self):
        if self.closed or self.db.storage_fault:
            return
        async with self.lock:
            await self.scan()
            jobs = await self.db.execute(
                lambda c: [
                    dict(r)
                    for r in c.execute(
                        "SELECT j.*,m.task_id FROM cleanup_jobs j JOIN material_copies m "
                        "USING(material_id) "
                        "WHERE j.state IN ('new','pending','deleting') AND "
                        "(next_attempt_at IS NULL OR next_attempt_at<=?)",
                        (timestamp(self.wall()),),
                    )
                ],
                write=False,
            )
            workers = [asyncio.create_task(self._clean(job)) for job in jobs]
            self.work.update(workers)
            try:
                await asyncio.gather(*workers)
            finally:
                self.work.difference_update(workers)

    async def _clean(self, job):
        async with self.slots:
            if self.closed:
                return
            await self._perform(job)

    async def _perform(self, job):
        def intent(c):
            material = dict(
                c.execute(
                    "SELECT * FROM material_copies WHERE material_id=?", (job["material_id"],)
                ).fetchone()
            )
            current = dict(
                c.execute(
                    "SELECT * FROM cleanup_jobs WHERE cleanup_id=?", (job["cleanup_id"],)
                ).fetchone()
            )
            if current["state"] == "new":
                current["remaining_budget"] = self.config.limits["CLEANUP_RETRIES"] + 1
            c.execute(
                "UPDATE cleanup_jobs SET state='deleting',remaining_budget=?,next_attempt_at=NULL "
                "WHERE cleanup_id=?",
                (max(0, current["remaining_budget"] - 1), job["cleanup_id"]),
            )
            c.execute(
                "UPDATE material_copies SET state='cleaning' WHERE material_id=?",
                (job["material_id"],),
            )
            row = _load(c, job["task_id"])
            _change(
                c,
                row,
                {"cleanup_state": "running"},
                kind="cleanup_attempt",
                now=timestamp(self.wall()),
            )
            c.execute(
                "INSERT INTO task_events(task_id,version,epoch,kind,recorded_at,details) "
                "VALUES (?,?,?,'cleanup_budget',?,?)",
                (
                    row["task_id"],
                    row["version"],
                    row["epoch"],
                    timestamp(self.wall()),
                    json.dumps(
                        {
                            "cleanup_id": job["cleanup_id"],
                            "remaining": max(0, current["remaining_budget"] - 1),
                        }
                    ),
                ),
            )
            return material, current

        material, current = await self.db.execute(intent)
        try:
            await self.readers.quiesce(
                job["task_id"], self.config.limits["REQUEST_TIMEOUT_SECONDS"]
            )
            if self.db.storage_fault:
                raise StorageError("STORAGE_FAULT")
            self.hook("cleanup_before_delete")
            # A deleting record with zero budget may only reconcile an absent file.
            if current["state"] == "deleting" and current["remaining_budget"] == 0:
                target = owned_path(self.root, material["material_id"] + ".input")
                if str(target) != material["managed_path"] or await self.readers.thread(
                    target.exists
                ):
                    raise RuntimeError("CLEANUP_RETRIES_EXHAUSTED")
            else:
                await self.readers.thread(delete_copy, self.root, material)
            self.hook("cleanup_after_delete")
        except StorageError:
            raise
        except asyncio.CancelledError:
            raise
        except (OSError, RuntimeError, pywintypes.error) as error:
            code = (
                str(error)
                if str(error)
                in {
                    "CLEANUP_FILE_BUSY_OR_DENIED",
                    "CLEANUP_OWNERSHIP_INVALID",
                    "CLEANUP_UNSAFE_FILE",
                    "CLEANUP_CONTENT_CHANGED",
                    "CLEANUP_DELETE_FAILED",
                    "CLEANUP_RETRIES_EXHAUSTED",
                    "MATERIAL_READERS_BUSY",
                }
                else "CLEANUP_PATH_OR_IO_ERROR"
            )
            await self._failure(job, code)
            return

        def complete(c):
            c.execute(
                "UPDATE cleanup_jobs SET state='done',result_code='CLEANED' WHERE cleanup_id=?",
                (job["cleanup_id"],),
            )
            c.execute(
                "UPDATE material_copies SET state='cleaned' WHERE material_id=?",
                (job["material_id"],),
            )
            c.execute(
                "UPDATE attempts SET state='reconciled',finished_at=? WHERE task_id=? "
                "AND phase='material_repair' AND state='intent'",
                (timestamp(self.wall()), job["task_id"]),
            )
            self._summary(c, job["task_id"])

        await self.db.execute(complete)

    async def _failure(self, job, code):
        def save(c):
            remaining = c.execute(
                "SELECT remaining_budget FROM cleanup_jobs WHERE cleanup_id=?", (job["cleanup_id"],)
            ).fetchone()[0]
            state = "pending" if remaining > 0 else "failed"
            c.execute(
                "UPDATE cleanup_jobs SET state=?,result_code=?,next_attempt_at=? "
                "WHERE cleanup_id=?",
                (
                    state,
                    code,
                    timestamp(
                        self.wall()
                        + min(
                            60, 2 ** min(6, self.config.limits["CLEANUP_RETRIES"] + 2 - remaining)
                        )
                    ),
                    job["cleanup_id"],
                ),
            )
            c.execute(
                "UPDATE material_copies SET state='cleanup_failed' WHERE material_id=?",
                (job["material_id"],),
            )
            self._summary(c, job["task_id"])

        await self.db.execute(save)

    async def retry(self, task_id, *, expected_version):
        async with self.lock:

            def reset(c):
                row = _load(c, task_id)
                jobs = c.execute(
                    "SELECT j.cleanup_id FROM cleanup_jobs j JOIN material_copies m "
                    "USING(material_id) WHERE m.task_id=? AND j.state='failed'",
                    (task_id,),
                ).fetchall()
                if not jobs:
                    if c.execute(
                        "SELECT 1 FROM cleanup_jobs j JOIN material_copies m USING(material_id) "
                        "WHERE m.task_id=?",
                        (task_id,),
                    ).fetchone():
                        return _public(row)
                    raise RuntimeError("MATERIAL_CLEANUP_NOT_AUTHORIZED")
                _version(row, expected_version)
                for job in jobs:
                    c.execute(
                        "UPDATE cleanup_jobs SET "
                        "state='pending',remaining_budget=?,next_attempt_at=NULL "
                        "WHERE cleanup_id=?",
                        (self.config.limits["CLEANUP_RETRIES"] + 1, job[0]),
                    )
                self._summary(c, task_id)
                return _public(_load(c, task_id))

            return await self.db.execute(reset)

    async def run(self, stop):
        while not stop.is_set() and not self.closed:
            await self.due()
            try:
                await asyncio.wait_for(stop.wait(), 0.05)
            except TimeoutError:
                pass

    async def close(self):
        self.closed = True
        workers = list(self.work)
        if workers:
            _, pending = await asyncio.wait(
                workers, timeout=self.config.limits["SHUTDOWN_DRAIN_SECONDS"]
            )
            for work in pending:
                work.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
