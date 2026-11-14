import asyncio
import sqlite3
import threading

import pytest

from zhenzhen_seedance_video.storage import Database, StorageError

TASK_SQL = """INSERT INTO tasks(task_id, request_key, api_id, model, kind, rule_version,
 intent_digest, effective_parameters, output_dir, connection_binding, created_at)
 VALUES (?, ?, 'seedance-video', 'synthetic-model', 't2v', '1', 'hash', '{}',
 'D:\\synthetic', 'binding', '2026-11-13T00:00:00Z')"""


@pytest.mark.asyncio
async def test_single_writer_persistence_constraints_and_pragmas(tmp_path):
    database = Database(tmp_path / "state")
    try:
        thread_ids = await asyncio.gather(
            *[database.execute(lambda connection: threading.get_ident()) for _ in range(20)]
        )
        assert len(set(thread_ids)) == 1
        assert thread_ids[0] != threading.get_ident()
        values = await database.execute(
            lambda c: [
                c.execute(f"PRAGMA {name}").fetchone()[0]
                for name in ("journal_mode", "synchronous", "foreign_keys", "user_version")
            ]
        )
        assert values == ["wal", 2, 1, 1]
        await database.execute(lambda c: c.execute(TASK_SQL, ("task1", "request1")).rowcount)
        with pytest.raises(StorageError, match="CONSTRAINT"):
            await database.execute(lambda c: c.execute(TASK_SQL, ("task2", "request1")).rowcount)
        with pytest.raises(StorageError, match="CONSTRAINT"):
            await database.execute(
                lambda c: (
                    c.execute(
                        "INSERT INTO diagnostics VALUES ('diag','missing','ERROR','now')"
                    ).rowcount
                )
            )
    finally:
        await database.close()
    restarted = Database(tmp_path / "state")
    try:
        assert (
            await restarted.execute(lambda c: c.execute("SELECT count(*) FROM tasks").fetchone()[0])
            == 1
        )
    finally:
        await restarted.close()


@pytest.mark.asyncio
async def test_transaction_failure_rolls_back_and_writer_survives(tmp_path):
    database = Database(tmp_path / "state")

    def operation(connection):
        connection.execute(TASK_SQL, ("task1", "request1"))
        raise ValueError("synthetic fault")

    try:
        with pytest.raises(ValueError, match="synthetic fault"):
            await database.execute(operation)
        assert (
            await database.execute(lambda c: c.execute("SELECT count(*) FROM tasks").fetchone()[0])
            == 0
        )
    finally:
        await database.close()


@pytest.mark.parametrize("payload", [b"broken database", b""])
def test_existing_invalid_database_not_replaced(tmp_path, payload):
    root = tmp_path / "state"
    root.mkdir()
    path = root / "tasks.sqlite3"
    path.write_bytes(payload)
    with pytest.raises(StorageError):
        Database(root)
    assert path.read_bytes() == payload


def test_future_schema_rejected_without_migration(tmp_path):
    root = tmp_path / "state"
    root.mkdir()
    path = root / "tasks.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version=999")
    before = path.read_bytes()
    with pytest.raises(StorageError, match="SCHEMA_INCOMPATIBLE"):
        Database(root)
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_cancelled_wait_does_not_cancel_accepted_transaction(tmp_path):
    database = Database(tmp_path / "state")
    entered = threading.Event()
    release = threading.Event()

    def operation(connection):
        entered.set()
        assert release.wait(timeout=5)
        connection.execute(TASK_SQL, ("task1", "request1"))

    try:
        waiter = asyncio.create_task(database.execute(operation))
        assert await asyncio.to_thread(entered.wait, 5)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        release.set()
        count = await database.execute(
            lambda c: c.execute("SELECT count(*) FROM tasks").fetchone()[0]
        )
        assert count == 1
    finally:
        release.set()
        await database.close()
    assert not database._thread.is_alive()


@pytest.mark.asyncio
async def test_domain_records_survive_restart(tmp_path):
    database = Database(tmp_path / "state")

    def populate(c):
        c.execute(TASK_SQL, ("task1", "request1"))
        c.execute("INSERT INTO admissions VALUES ('request2','op','digest',12,'[]','now')")
        c.execute("""INSERT INTO attempts(attempt_id,task_id,phase,round,epoch,state,
                  started_at,remaining_budget)
                  VALUES ('a','task1','submit',1,0,'intent','now',0)""")
        c.execute("""INSERT INTO remote_observations(observation_id,task_id,attempt_id,epoch,
                  raw_status,observed_at,source,facts)
                  VALUES ('o','task1','a',0,'queued','now','synthetic','{}')""")
        c.execute("INSERT INTO material_copies VALUES ('m','task1','managed','hash',12,'ready',0)")
        c.execute(
            "INSERT INTO uploads VALUES ('u','m','binding','https://example.test',NULL,3,'ready')"
        )
        c.execute("""INSERT INTO artifacts(artifact_id,task_id,required,target_path,state)
                  VALUES ('v','task1',1,'target','pending')""")
        c.execute("""INSERT INTO cleanup_jobs(cleanup_id,material_id,reason,remaining_budget,state)
                  VALUES ('c','m','failed',3,'pending')""")
        c.execute("INSERT INTO preferences VALUES ('enhance_prompt','false',1,'user','now',NULL)")
        c.execute("""INSERT INTO task_events(task_id,version,epoch,kind,recorded_at,details)
                  VALUES ('task1',1,0,'created','now','{}')""")
        c.execute("INSERT INTO diagnostics VALUES ('d','task1','ERROR','now')")

    await database.execute(populate)
    await database.close()
    restarted = Database(tmp_path / "state")
    try:

        def counts(c):
            tables = [
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
            ]
            return [c.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in tables]

        assert await restarted.execute(counts) == [1] * 11
    finally:
        await restarted.close()


async def test_missing_database_with_initialization_history_is_not_recreated(tmp_path):
    root = tmp_path / "state"
    database = Database(root)
    await database.close()
    database.path.unlink()
    with pytest.raises(StorageError, match="DATABASE_MISSING_WITH_HISTORY"):
        Database(root)
    assert not database.path.exists()


async def test_offline_consistent_backup_preserves_unknown_task(tmp_path):
    root = tmp_path / "state"
    database = Database(root)
    await database.execute(lambda c: c.execute(TASK_SQL, ("t", "request")).rowcount)
    await database.execute(
        lambda c: (
            c.execute(
                "UPDATE tasks SET remote_state='unknown',stage='submitting',generation_slot_held=1"
            ).rowcount
        )
    )
    await database.close()
    backup_root = tmp_path / "backup-state"
    backup_root.mkdir()
    backup_path = backup_root / "tasks.sqlite3"
    with sqlite3.connect(database.path.as_uri() + "?mode=ro", uri=True) as source:
        with sqlite3.connect(backup_path) as target:
            source.backup(target)
            assert target.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    restored = Database(backup_root)
    try:
        result = await restored.execute(
            lambda c: c.execute(
                "SELECT request_key,remote_state,generation_slot_held FROM tasks"
            ).fetchone()[:],
            write=False,
        )
        assert result == ("request", "unknown", 1)
    finally:
        await restored.close()
