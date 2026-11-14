import asyncio
import json

import pytest

from zhenzhen_seedance_video.provider_response import decode_response
from zhenzhen_seedance_video.storage import Database
from zhenzhen_seedance_video.task_state import StateError, TaskState


@pytest.fixture
async def state(tmp_path):
    database = Database(tmp_path / "state")
    await database.execute(
        lambda c: (
            c.execute("""INSERT INTO tasks(task_id,request_key,api_id,
        model,kind,rule_version,intent_digest,effective_parameters,output_dir,connection_binding,created_at)
        VALUES ('t','r','seedance-video','synthetic','t2v','1','digest','{}',
                'D:\\test','b','now')""").rowcount
        )
    )
    try:
        yield TaskState(database)
    finally:
        await database.close()


def observation(status):
    return decode_response(
        json.dumps(
            {
                "id": "remote",
                "object": "video",
                "model": "synthetic",
                "status": status,
                "metadata": {"url": "https://example.com/v.mp4"},
            }
        ).encode(),
        expected_model="synthetic",
    )


async def test_success_is_not_ready_and_identical_observation_keeps_version(state):
    first = await state.observe("t", observation("completed"), operation_epoch=0, now="1")
    assert first["remote_state"] == "succeeded"
    assert first["delivery"] == "pending"
    assert first["stage"] == "downloading"
    second = await state.observe("t", observation("completed"), operation_epoch=0, now="2")
    assert second["version"] == first["version"]


async def test_cancel_is_local_and_repeated_action_noop(state):
    first = await state.cancel_unsubmitted("t", expected_version=1, now="1")
    assert first["locally_cancelled"] == 1
    assert first["remote_state"] == "not_submitted"
    assert first["cleanup_state"] == "pending"
    assert await state.cancel_unsubmitted("t", expected_version=1, now="2") == first


async def test_competing_management_actions_have_one_winner(state):
    outcomes = await asyncio.gather(
        state.cancel_unsubmitted("t", expected_version=1, now="1"),
        state.abandon("t", expected_version=1, reason="user request", confirmed=True, now="1"),
        return_exceptions=True,
    )
    assert sum(isinstance(item, StateError) for item in outcomes) == 1
    error = next(item for item in outcomes if isinstance(item, StateError))
    assert str(error) == "VERSION_CONFLICT"
    assert error.snapshot["version"] == 2


async def test_abandon_then_late_success_does_not_resume_download(state):
    await state.database.execute(
        lambda c: (
            c.execute(
                "UPDATE tasks SET stage='tracking',remote_state='running',generation_slot_held=1"
            ).rowcount
        )
    )
    abandoned = await state.abandon("t", expected_version=1, reason="stop", confirmed=True, now="1")
    assert abandoned["remote_state"] == "running"
    assert abandoned["generation_slot_held"] == 0
    assert (
        await state.abandon("t", expected_version=1, reason="stop", confirmed=True, now="2")
        == abandoned
    )
    late = await state.observe("t", observation("completed"), operation_epoch=0, now="3")
    assert late["remote_state"] == "succeeded"
    assert late["remote_id"] == "remote"
    assert late["auto_mode"] == "abandoned"
    assert late["delivery"] == "none"
    assert late["stage"] != "downloading"
    assert late["generation_slot_held"] == 0


async def test_terminal_conflict_preserves_confirmed_fact(state):
    await state.observe("t", observation("completed"), operation_epoch=0, now="1")
    conflict = await state.observe("t", observation("failed"), operation_epoch=0, now="2")
    assert conflict["remote_state"] == "succeeded"
    assert conflict["auto_mode"] == "needs_attention"
    assert "REMOTE_TERMINAL_CONFLICT" in conflict["attention"]


async def test_started_submission_cannot_be_locally_cancelled(state):
    await state.database.execute(
        lambda c: c.execute("UPDATE tasks SET stage='submitting'").rowcount
    )
    with pytest.raises(StateError, match="CAPABILITY_UNVERIFIED"):
        await state.cancel_unsubmitted("t", expected_version=1, now="1")


async def test_slot_and_intent_are_atomic_and_persist_unknown(state):
    result = await state.begin_submission(
        "t", expected_version=1, connection_binding="b", limit=1, now="1", deadline="later"
    )
    assert result["generation_slot_held"] == 1
    assert result["remote_state"] == "unknown"
    assert (
        await state.database.execute(
            lambda c: c.execute(
                "SELECT state FROM attempts WHERE attempt_id=?", (result["attempt_id"],)
            ).fetchone()[0]
        )
        == "intent"
    )
    with pytest.raises(StateError, match="VERSION_CONFLICT"):
        await state.begin_submission(
            "t", expected_version=1, connection_binding="b", limit=1, now="2", deadline="later"
        )
    assert (
        await state.database.execute(
            lambda c: c.execute("SELECT count(*) FROM attempts").fetchone()[0]
        )
        == 1
    )
    completed = await state.observe("t", observation("completed"), operation_epoch=0, now="3")
    assert completed["generation_slot_held"] == 0


async def test_running_to_queued_preserves_fact_and_slot(state):
    await state.begin_submission(
        "t", expected_version=1, connection_binding="b", limit=1, now="1", deadline="later"
    )
    await state.observe("t", observation("in_progress"), operation_epoch=0, now="2")
    result = await state.observe("t", observation("queued"), operation_epoch=0, now="3")
    assert result["remote_state"] == "running"
    assert result["generation_slot_held"] == 1
    assert result["auto_mode"] == "needs_attention"
    assert "REMOTE_STATE_REGRESSION" in result["attention"]
