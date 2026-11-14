"""Persist already-verified actual charges; not an upstream envelope decoder."""

import json
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ActualCharge:
    amount: Decimal | None
    currency: str | None
    raw_status: str
    evidence_digest: str

    def __post_init__(self):
        if self.amount is not None and (
            not isinstance(self.amount, Decimal) or not self.amount.is_finite() or self.amount < 0
        ):
            raise ValueError("INVALID_ACTUAL_AMOUNT")
        if self.currency is not None and (
            not isinstance(self.currency, str)
            or not (
                self.currency == "¥"
                or (
                    self.currency.isascii()
                    and self.currency.isalpha()
                    and len(self.currency) == 3
                    and self.currency == self.currency.upper()
                )
            )
        ):
            raise ValueError("INVALID_ACTUAL_CURRENCY")
        if self.raw_status not in ("SUCCESS", "completed", "failed"):
            raise ValueError("UNVERIFIED_CHARGE_STATUS")
        if len(self.evidence_digest) != 64 or any(
            char not in "0123456789abcdef" for char in self.evidence_digest
        ):
            raise ValueError("INVALID_EVIDENCE_DIGEST")


async def record_actual_charge(database, task_id, charge: ActualCharge, *, now):
    """Only a verified fee adapter may call this, never arbitrary request fields.

    Missing values do not overwrite a prior complete charge. A later complete
    value replaces the previous value, including explicit refund zero.
    """

    return await database.execute(lambda c: record_charge_transaction(c, task_id, charge, now=now))


def record_charge_transaction(c, task_id, charge: ActualCharge, *, now):
    """Persist within the terminal observation transaction when called by the parser path."""
    from .task_state import StateError, _change, _load

    row = _load(c, task_id)
    if row["remote_state"] not in ("succeeded", "failed"):
        raise StateError("CHARGE_BEFORE_CONFIRMED_TERMINAL")
    c.execute(
        """INSERT OR IGNORE INTO charge_observations
           (task_id,evidence_digest,raw_status,amount,currency,observed_at)
           VALUES (?,?,?,?,?,?)""",
        (
            task_id,
            charge.evidence_digest,
            charge.raw_status,
            str(charge.amount) if charge.amount is not None else None,
            charge.currency,
            now,
        ),
    )
    complete = charge.amount is not None and charge.currency is not None
    updates = {}
    if complete:
        amount_text = str(charge.amount)
        if row["actual_amount"] is not None and Decimal(row["actual_amount"]) == charge.amount:
            amount_text = row["actual_amount"]
        updates.update(
            actual_amount=amount_text,
            actual_currency=charge.currency,
            charge_state="confirmed",
        )
    elif row["charge_state"] != "confirmed":
        updates["charge_state"] = "incomplete"
    before = row["version"]
    _change(c, row, updates, kind="actual_charge", now=now)
    if row["version"] != before:
        c.execute(
            "UPDATE task_events SET details=? WHERE event_id=last_insert_rowid()",
            (
                json.dumps(
                    {"raw_status": charge.raw_status, "evidence_digest": charge.evidence_digest}
                ),
            ),
        )
    return {
        "state": row["charge_state"],
        "amount": row["actual_amount"],
        "currency": row["actual_currency"],
        "version": row["version"],
    }
