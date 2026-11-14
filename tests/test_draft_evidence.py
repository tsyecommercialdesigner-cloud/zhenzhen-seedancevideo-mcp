import json

import pytest
import test_admission
import test_tools
from test_tools import call, protocol

from zhenzhen_seedance_video.compatibility_adapter import CompatibilityAdapter
from zhenzhen_seedance_video.parameters import ParameterError
from zhenzhen_seedance_video.provider import ProviderFailure
from zhenzhen_seedance_video.tools import Tools

intake = test_admission.intake
surface = test_tools.surface


FINAL = {
    "model": "seedance-2.5-standard-draft-to-video",
    "metadata": {"draft_task_id": "local-draft"},
}


async def source(service, *, key="source", prefix="", draft=True, state="succeeded", binding=None):
    accepted = await service.submit(
        key,
        {
            "model": f"seedance-2.5-{prefix}standard-t2v",
            "prompt": "synthetic cube",
            "metadata": {"draft": draft},
        },
    )
    await service.db.execute(
        lambda c: c.execute(
            "UPDATE tasks SET remote_id='local-draft',remote_state=?,connection_binding=? "
            "WHERE task_id=?",
            (state, binding or service.binding, accepted["task_id"]),
        )
    )
    return accepted["task_id"]


@pytest.mark.parametrize(
    "kwargs",
    [{"prefix": "global-"}, {"draft": False}, {"state": "running"}, {"state": "failed"}],
)
async def test_known_local_invalid_rejected_by_preflight_and_admission(intake, kwargs):
    await source(intake, **kwargs)
    tools = Tools(intake, None, None)
    with pytest.raises(ParameterError, match="DRAFT_NOT_ELIGIBLE"):
        await tools.preflight_video_task(FINAL)
    with pytest.raises(ParameterError, match="DRAFT_NOT_ELIGIBLE"):
        await intake.submit("final", FINAL)
    assert (await intake.find("final"))["status"] == "not_found"
    assert (
        await intake.db.execute(
            lambda c: c.execute("SELECT count(*) FROM admissions").fetchone()[0], write=False
        )
        == 0
    )


@pytest.mark.parametrize("kind", ["external", "other-binding", "ambiguous"])
async def test_unverifiable_source_stays_unknown(intake, kind):
    if kind == "other-binding":
        await source(intake, draft=False, binding="different-connection")
    if kind == "ambiguous":
        await source(intake)
        await source(intake, key="duplicate", draft=False)
    pre = await Tools(intake, None, None).preflight_video_task(FINAL)
    accepted = await intake.submit("final", FINAL)
    for result in (pre, accepted):
        assert {
            "DRAFT_SOURCE_UNVERIFIED",
            "DRAFT_ACCOUNT_UNVERIFIED",
            "DRAFT_VALIDITY_ANCHOR_UNVERIFIED",
        } <= set(result["unverified"])


async def test_acceptance_rechecks_after_preflight_and_replay_preserves_task(intake):
    tid = await source(intake)
    tools = Tools(intake, None, None)
    pre = await tools.preflight_video_task(FINAL)
    assert "DRAFT_SOURCE_UNVERIFIED" not in pre["unverified"]
    assert "DRAFT_ACCOUNT_UNVERIFIED" in pre["unverified"]
    assert "DRAFT_VALIDITY_ANCHOR_UNVERIFIED" in pre["unverified"]
    await intake.db.execute(
        lambda c: c.execute("UPDATE tasks SET remote_state='failed' WHERE task_id=?", (tid,))
    )
    with pytest.raises(ParameterError, match="DRAFT_NOT_ELIGIBLE"):
        await intake.submit("final", FINAL)
    await intake.db.execute(
        lambda c: c.execute("UPDATE tasks SET remote_state='succeeded' WHERE task_id=?", (tid,))
    )
    accepted = await intake.submit("final", FINAL)
    await intake.db.execute(
        lambda c: c.execute("UPDATE tasks SET remote_state='failed' WHERE task_id=?", (tid,))
    )
    replay = await intake.submit("final", FINAL)
    assert replay["task_id"] == accepted["task_id"]
    row = await intake.db.execute(
        lambda c: dict(
            c.execute("SELECT * FROM tasks WHERE task_id=?", (accepted["task_id"],)).fetchone()
        ),
        write=False,
    )
    adapter = CompatibilityAdapter(None, intake.db)
    with pytest.raises(ProviderFailure, match="DRAFT_NOT_ELIGIBLE"):
        await adapter.prepare(row)
    assert "output_format" not in json.loads(row["effective_parameters"])["metadata"]
    assert (
        await intake.db.execute(
            lambda c: c.execute("SELECT count(*) FROM attempts").fetchone()[0], write=False
        )
        == 0
    )


async def test_stdio_preflight_and_submit_use_local_facts(surface):
    facade, _, _ = surface
    await source(facade.admission, prefix="global-")
    async with protocol() as session:
        for name, arguments in (
            ("preflight_video_task", {"request": FINAL}),
            ("submit_video", {"request_key": "wrong-region", "request": FINAL}),
        ):
            result = await session.call_tool(name, arguments)
            assert result.structured_content["ok"] is False
            assert result.structured_content["error"] == "DRAFT_NOT_ELIGIBLE"
        unknown = FINAL | {"metadata": {"draft_task_id": "external-draft"}}
        pre = await call(session, "preflight_video_task", request=unknown)
        assert "DRAFT_SOURCE_UNVERIFIED" in pre["unverified"]
