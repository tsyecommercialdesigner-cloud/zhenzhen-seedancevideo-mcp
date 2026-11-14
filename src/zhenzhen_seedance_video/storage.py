"""One dedicated SQLite thread; cancelled callers do not undo committed work."""

import asyncio
import concurrent.futures
import os
import queue
import sqlite3
import threading
from pathlib import Path

from .windows_security import protect_directory, reject_reparse_path

SCHEMA_VERSION = 1
SCHEMA = """
CREATE TABLE tasks (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT,
 task_id TEXT NOT NULL UNIQUE,
 request_key TEXT NOT NULL UNIQUE,
 api_id TEXT NOT NULL,
 model TEXT NOT NULL,
 kind TEXT NOT NULL,
 rule_version TEXT NOT NULL,
 intent_digest TEXT NOT NULL,
 effective_parameters TEXT NOT NULL CHECK(json_valid(effective_parameters)),
 output_dir TEXT NOT NULL,
 connection_binding TEXT NOT NULL,
 stage TEXT NOT NULL DEFAULT 'queued' CHECK(stage IN
 ('queued','preparing','submitting','tracking','downloading','settled')),
 remote_state TEXT NOT NULL DEFAULT 'not_submitted' CHECK(remote_state IN
 ('not_submitted','unknown','queued','running','succeeded','failed','cancelled')),
 remote_id TEXT,
 auto_mode TEXT NOT NULL DEFAULT 'active' CHECK(auto_mode IN
 ('active','needs_attention','abandoned')),
 delivery TEXT NOT NULL DEFAULT 'none' CHECK(delivery IN
 ('none','pending','partial','ready','missing','changed')),
 cleanup_state TEXT NOT NULL DEFAULT 'none',
 attention TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(attention)),
 cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK(cancel_requested IN (0,1)),
 locally_cancelled INTEGER NOT NULL DEFAULT 0 CHECK(locally_cancelled IN (0,1)),
 generation_slot_held INTEGER NOT NULL DEFAULT 0 CHECK(generation_slot_held IN (0,1)),
 tracking_round INTEGER NOT NULL DEFAULT 0,
 version INTEGER NOT NULL DEFAULT 1 CHECK(version > 0),
 epoch INTEGER NOT NULL DEFAULT 0 CHECK(epoch >= 0),
 tracking_started_at TEXT,
 tracking_deadline TEXT,
 last_observed_at TEXT,
 actual_amount TEXT,
 actual_currency TEXT,
 charge_state TEXT NOT NULL DEFAULT 'not_returned',
 created_at TEXT NOT NULL
);
CREATE TABLE admissions (
 request_key TEXT PRIMARY KEY,
 operation_id TEXT NOT NULL UNIQUE,
 intent_digest TEXT NOT NULL,
 reserved_bytes INTEGER NOT NULL CHECK(reserved_bytes >= 0),
 temporary_materials TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(temporary_materials)),
 created_at TEXT NOT NULL
);
CREATE TABLE attempts (
 attempt_id TEXT PRIMARY KEY,
 task_id TEXT NOT NULL REFERENCES tasks(task_id),
 phase TEXT NOT NULL,
 round INTEGER NOT NULL,
 epoch INTEGER NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('intent','finished','reconciled')),
 started_at TEXT NOT NULL,
 finished_at TEXT,
 remaining_budget INTEGER NOT NULL CHECK(remaining_budget >= 0),
 next_attempt_at TEXT,
 remote_id TEXT,
 evidence_digest TEXT
 ,effect_started INTEGER NOT NULL DEFAULT 0 CHECK(effect_started IN (0,1))
);
CREATE TABLE remote_observations (
 observation_id TEXT PRIMARY KEY,
 task_id TEXT NOT NULL REFERENCES tasks(task_id),
 attempt_id TEXT REFERENCES attempts(attempt_id),
 epoch INTEGER NOT NULL,
 remote_id TEXT,
 raw_status TEXT NOT NULL,
 observed_at TEXT NOT NULL,
 source TEXT NOT NULL,
 facts TEXT NOT NULL CHECK(json_valid(facts)),
 terminal_conflict INTEGER NOT NULL DEFAULT 0 CHECK(terminal_conflict IN (0,1))
);
CREATE TABLE material_copies (
 material_id TEXT PRIMARY KEY,
 task_id TEXT NOT NULL REFERENCES tasks(task_id),
 managed_path TEXT NOT NULL UNIQUE,
 sha256 TEXT NOT NULL,
 size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
 state TEXT NOT NULL,
 ordinal INTEGER NOT NULL,
 UNIQUE(task_id,ordinal)
);
CREATE TABLE uploads (
 upload_id TEXT PRIMARY KEY,
 material_id TEXT NOT NULL REFERENCES material_copies(material_id),
 connection_binding TEXT NOT NULL,
 url TEXT NOT NULL,
 expires_at TEXT,
 remaining_budget INTEGER NOT NULL CHECK(remaining_budget >= 0),
 state TEXT NOT NULL
);
CREATE TABLE artifacts (
 artifact_id TEXT PRIMARY KEY,
 task_id TEXT NOT NULL REFERENCES tasks(task_id),
 source_url TEXT,
 required INTEGER NOT NULL CHECK(required IN (0,1)),
 target_path TEXT NOT NULL UNIQUE,
 temporary_path TEXT,
 sha256 TEXT,
 size_bytes INTEGER,
 state TEXT NOT NULL
);
CREATE TABLE cleanup_jobs (
 cleanup_id TEXT PRIMARY KEY,
 material_id TEXT NOT NULL REFERENCES material_copies(material_id),
 reason TEXT NOT NULL,
 remaining_budget INTEGER NOT NULL CHECK(remaining_budget >= 0),
 state TEXT NOT NULL,
 next_attempt_at TEXT,
 result_code TEXT
);
CREATE TABLE preferences (
 name TEXT PRIMARY KEY,
 value TEXT NOT NULL CHECK(json_valid(value)),
 version INTEGER NOT NULL CHECK(version > 0),
 source TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 revoked_at TEXT
);
CREATE TABLE task_events (
 event_id INTEGER PRIMARY KEY AUTOINCREMENT,
 task_id TEXT NOT NULL REFERENCES tasks(task_id),
 version INTEGER NOT NULL,
 epoch INTEGER NOT NULL,
 kind TEXT NOT NULL,
 recorded_at TEXT NOT NULL,
 details TEXT NOT NULL CHECK(json_valid(details))
);
CREATE TABLE diagnostics (
 diagnostic_id TEXT PRIMARY KEY,
 task_id TEXT REFERENCES tasks(task_id),
 code TEXT NOT NULL,
 recorded_at TEXT NOT NULL
);
CREATE TABLE charge_observations (
 task_id TEXT NOT NULL REFERENCES tasks(task_id),
 evidence_digest TEXT NOT NULL,
 raw_status TEXT NOT NULL,
 amount TEXT,
 currency TEXT,
 observed_at TEXT NOT NULL,
 PRIMARY KEY(task_id,evidence_digest)
);
CREATE INDEX attempts_pending ON attempts(state, task_id);
CREATE INDEX tasks_dispatch ON tasks(stage, auto_mode, sequence);
"""


class StorageError(RuntimeError):
    pass


class Database:
    """Instantiate during startup (off the event loop), under the ownership lock.

    Transaction functions are internal synchronous functions and must not perform
    network/file side effects. They return detached values, never cursors.
    """

    def __init__(self, directory: Path, *, queue_limit=128, busy_timeout_ms=2000):
        if queue_limit < 1 or busy_timeout_ms < 1:
            raise ValueError("INVALID_STORAGE_LIMIT")
        protect_directory(directory)
        self.path = directory / "tasks.sqlite3"
        self.marker = directory / "database.initialized"
        reject_reparse_path(self.marker)
        for suffix in ("", "-wal", "-shm"):
            reject_reparse_path(Path(str(self.path) + suffix))
        self._queue = queue.Queue(maxsize=queue_limit)
        self._closed = False
        self._fault = threading.Event()
        self._submit_lock = threading.Lock()
        self._ready = concurrent.futures.Future()
        self._thread = threading.Thread(
            target=self._run, args=(busy_timeout_ms,), name="video-sqlite-writer", daemon=False
        )
        self._thread.start()
        self._ready.result()

    def _open(self, timeout):
        existing = self.path.exists()
        if not existing:
            if self.marker.exists() or any(
                Path(str(self.path) + suffix).exists() for suffix in ("-wal", "-shm")
            ):
                raise StorageError("DATABASE_MISSING_WITH_HISTORY")
            # Persist first: interrupted initialization must not silently restart
            # as an empty database on the next startup.
            with self.marker.open("xb") as marker:
                marker.write(b"initial-schema-1\n")
                marker.flush()
                os.fsync(marker.fileno())
        mode = "rw" if existing else "rwc"
        connection = sqlite3.connect(
            self.path.as_uri() + f"?mode={mode}", uri=True, isolation_level=None
        )
        try:
            connection.row_factory = sqlite3.Row
            connection.execute(f"PRAGMA busy_timeout={timeout}")
            if existing:
                if connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                    raise StorageError("SCHEMA_INCOMPATIBLE")
                if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise StorageError("DATABASE_CORRUPT")
                required = {
                    "tasks",
                    "admissions",
                    "attempts",
                    "remote_observations",
                    "material_copies",
                    "uploads",
                    "artifacts",
                    "cleanup_jobs",
                    "preferences",
                    "task_events",
                    "diagnostics",
                    "charge_observations",
                }
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                if not required <= tables:
                    raise StorageError("SCHEMA_INCOMPATIBLE")
            if connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] != "wal":
                raise StorageError("WAL_UNAVAILABLE")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA foreign_keys=ON")
            if not existing:
                connection.executescript(
                    "BEGIN IMMEDIATE;" + SCHEMA + f"PRAGMA user_version={SCHEMA_VERSION};COMMIT;"
                )
            if not self.marker.exists():
                with self.marker.open("xb") as marker:
                    marker.write(b"initial-schema-1\n")
                    marker.flush()
                    os.fsync(marker.fileno())
            return connection
        except BaseException:
            connection.close()
            raise

    def _run(self, timeout):
        try:
            connection = self._open(timeout)
        except Exception as error:
            code = str(error) if isinstance(error, StorageError) else "DATABASE_OPEN_FAILED"
            self._ready.set_exception(StorageError(code))
            return
        self._ready.set_result(None)
        try:
            while True:
                item = self._queue.get()
                if item is None:
                    return
                function, future, write = item
                recovering = write == "reconcile"
                if write and self._fault.is_set() and not recovering:
                    future.set_exception(StorageError("STORAGE_FAULT"))
                    continue
                try:
                    connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
                    if (
                        recovering
                        and connection.execute("PRAGMA quick_check").fetchone()[0] != "ok"
                    ):
                        raise StorageError("DATABASE_CORRUPT")
                    result = function(connection)
                    if (
                        recovering
                        and connection.execute(
                            "SELECT count(*) FROM attempts WHERE state='intent'"
                        ).fetchone()[0]
                    ):
                        raise StorageError("RECONCILIATION_REQUIRED")
                    connection.execute("COMMIT")
                except BaseException as error:
                    failure = error
                    if connection.in_transaction:
                        try:
                            connection.rollback()
                        except sqlite3.Error:
                            failure = StorageError("STORAGE_FAULT")
                    if isinstance(failure, sqlite3.DatabaseError) and not isinstance(
                        failure, sqlite3.IntegrityError
                    ):
                        self._fault.set()
                    if isinstance(failure, StorageError) and str(failure) == "STORAGE_FAULT":
                        self._fault.set()
                    if isinstance(failure, sqlite3.Error):
                        code = (
                            "STORAGE_CONSTRAINT"
                            if isinstance(failure, sqlite3.IntegrityError)
                            else "STORAGE_FAULT"
                        )
                        failure = StorageError(code)
                    future.set_exception(failure)
                else:
                    if recovering:
                        self._fault.clear()
                    future.set_result(result)
        finally:
            connection.close()

    async def execute(self, function, *, write=True):
        future = concurrent.futures.Future()
        with self._submit_lock:
            if self._closed:
                raise StorageError("DATABASE_CLOSED")
            try:
                self._queue.put_nowait((function, future, write))
            except queue.Full:
                raise StorageError("STORAGE_QUEUE_FULL") from None
        wrapped = asyncio.wrap_future(future)
        # Retrieve a later exception even if the waiter was cancelled.
        wrapped.add_done_callback(lambda done: done.exception() if not done.cancelled() else None)
        return await asyncio.shield(wrapped)

    @property
    def storage_fault(self):
        return self._fault.is_set()

    async def pending_intents(self):
        return await self.execute(
            lambda c: [
                dict(row)
                for row in c.execute(
                    "SELECT attempt_id,task_id,phase,epoch,effect_started FROM attempts "
                    "WHERE state='intent' ORDER BY started_at,attempt_id"
                )
            ],
            write=False,
        )

    async def reconcile(self, function):
        """Internal recovery coordinator only: inspect/resolve intents transactionally.

        No boolean 'verified' flag from an Agent can clear this gate. Unresolved
        intent records prevent reopening even when the database is writable.
        """
        self._fault.set()
        return await self.execute(function, write="reconcile")

    async def run_effect(self, attempt_id, effect):
        """Start an effect only from a committed, current intent and healthy store.

        In-flight effects may finish after a fault, but their results must still
        be persisted before downstream work or quota release is authorized.
        """

        def check(c):
            row = c.execute(
                """SELECT a.state,a.epoch,t.epoch,t.auto_mode,a.effect_started FROM attempts a
                   JOIN tasks t ON a.task_id=t.task_id WHERE a.attempt_id=?""",
                (attempt_id,),
            ).fetchone()
            if (
                row is None
                or row[0] != "intent"
                or row[1] != row[2]
                or row[3] != "active"
                or row[4]
            ):
                raise StorageError("EFFECT_NOT_AUTHORIZED")
            c.execute("UPDATE attempts SET effect_started=1 WHERE attempt_id=?", (attempt_id,))

        await self.execute(check)
        if self._fault.is_set():
            raise StorageError("STORAGE_FAULT")
        return await effect()

    async def close(self):
        with self._submit_lock:
            first = not self._closed
            self._closed = True
        if first:
            await asyncio.to_thread(self._queue.put, None)
        await asyncio.to_thread(self._thread.join)
