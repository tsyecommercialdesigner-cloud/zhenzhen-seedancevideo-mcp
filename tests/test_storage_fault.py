import pytest

from zhenzhen_seedance_video.storage import Database, StorageError


@pytest.fixture
async def database(tmp_path):
    db = Database(tmp_path / "state")

    def setup(c):
        c.execute("""INSERT INTO tasks(task_id,request_key,api_id,model,kind,rule_version,
          intent_digest,effective_parameters,output_dir,connection_binding,created_at,
          generation_slot_held,stage,remote_state)
          VALUES ('t','r','seedance-video','synthetic','t2v','1','hash','{}',
          'D:\\test','binding','now',1,'submitting','unknown')""")
        c.execute("""INSERT INTO attempts(attempt_id,task_id,phase,round,epoch,state,
          started_at,remaining_budget) VALUES ('a','t','submit',1,0,'intent','now',0)""")

    await db.execute(setup)
    try:
        yield db
    finally:
        await db.close()


async def test_storage_error_stops_writes_and_new_side_effects(database):
    def fail(c):
        c.execute("UPDATE tasks SET generation_slot_held=0")
        c.execute("SELECT * FROM nonexistent_table")

    with pytest.raises(StorageError, match="STORAGE_FAULT"):
        await database.execute(fail)
    assert database.storage_fault
    pending = await database.pending_intents()
    assert len(pending) == 1
    assert pending[0]["attempt_id"] == "a"
    assert (
        await database.execute(
            lambda c: c.execute("SELECT generation_slot_held FROM tasks").fetchone()[0], write=False
        )
        == 1
    )
    called = []

    async def effect():
        called.append("called")

    with pytest.raises(StorageError, match="STORAGE_FAULT"):
        await database.run_effect("a", effect)
    with pytest.raises(StorageError, match="STORAGE_FAULT"):
        await database.execute(lambda c: c.execute("DELETE FROM attempts").rowcount)
    assert called == []
    with pytest.raises(StorageError, match="RECONCILIATION_REQUIRED"):
        await database.reconcile(lambda c: None)
    assert database.storage_fault

    def reconcile(c):
        c.execute("UPDATE attempts SET state='reconciled'")
        c.execute("UPDATE tasks SET auto_mode='needs_attention'")

    await database.reconcile(reconcile)
    assert not database.storage_fault
    assert (
        await database.execute(
            lambda c: c.execute("SELECT generation_slot_held FROM tasks").fetchone()[0], write=False
        )
        == 1
    )


async def test_effect_requires_durable_current_intent(database):
    called = []

    async def effect():
        called.append("called")
        return "result"

    assert await database.run_effect("a", effect) == "result"
    with pytest.raises(StorageError, match="EFFECT_NOT_AUTHORIZED"):
        await database.run_effect("a", effect)
    await database.execute(lambda c: c.execute("UPDATE tasks SET epoch=1").rowcount)
    with pytest.raises(StorageError, match="EFFECT_NOT_AUTHORIZED"):
        await database.run_effect("a", effect)
    with pytest.raises(StorageError, match="EFFECT_NOT_AUTHORIZED"):
        await database.run_effect("nonexistent", effect)
    assert called == ["called"]
