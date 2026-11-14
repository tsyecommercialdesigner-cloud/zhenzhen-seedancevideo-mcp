from decimal import Decimal

import pytest

from zhenzhen_seedance_video.charges import ActualCharge, record_actual_charge
from zhenzhen_seedance_video.storage import Database


@pytest.fixture
async def charged_database(tmp_path):
    database = Database(tmp_path / "state")
    await database.execute(
        lambda c: (
            c.execute("""INSERT INTO tasks(task_id,request_key,api_id,
        model,kind,rule_version,intent_digest,effective_parameters,output_dir,
        connection_binding,created_at,remote_state,delivery)
        VALUES ('t','r','seedance-video','synthetic','t2v','1','digest','{}',
        'D:\\test','b','now','succeeded','ready')""").rowcount
        )
    )
    try:
        yield database
    finally:
        await database.close()


async def test_actual_amount_is_decimal_replaced_not_accumulated(charged_database):
    charge = ActualCharge(Decimal("8.750000000000000000001"), "CNY", "completed", "a" * 64)
    first = await record_actual_charge(charged_database, "t", charge, now="1")
    second = await record_actual_charge(charged_database, "t", charge, now="2")
    assert first == second
    assert first["amount"] == "8.750000000000000000001"
    refund = ActualCharge(Decimal("0"), "CNY", "failed", "b" * 64)
    result = await record_actual_charge(charged_database, "t", refund, now="3")
    assert result["amount"] == "0"
    assert (
        await charged_database.execute(
            lambda c: c.execute("SELECT delivery FROM tasks WHERE task_id='t'").fetchone()[0]
        )
        == "ready"
    )


@pytest.mark.parametrize("amount,currency", [(None, None), (Decimal("8.75"), None), (None, "CNY")])
async def test_missing_fee_is_not_zero_or_artifact_failure(charged_database, amount, currency):
    charge = ActualCharge(amount, currency, "completed", "a" * 64)
    result = await record_actual_charge(charged_database, "t", charge, now="1")
    assert result["state"] == "incomplete"
    assert result["amount"] is None
    assert await charged_database.execute(
        lambda c: c.execute("SELECT remote_state,delivery FROM tasks").fetchone()[:]
    ) == ("succeeded", "ready")


async def test_missing_later_fee_keeps_last_confirmed_value(charged_database):
    first = await record_actual_charge(
        charged_database, "t", ActualCharge(Decimal("8.75"), "CNY", "completed", "a" * 64), now="1"
    )
    later = await record_actual_charge(
        charged_database, "t", ActualCharge(None, None, "completed", "b" * 64), now="2"
    )
    assert later == first


@pytest.mark.parametrize("amount", [8.75, Decimal("NaN"), Decimal("Infinity"), Decimal("-1")])
def test_non_exact_or_invalid_amount_rejected(amount):
    with pytest.raises(ValueError, match="AMOUNT"):
        ActualCharge(amount, "CNY", "completed", "a" * 64)
