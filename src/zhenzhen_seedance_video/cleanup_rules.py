"""Persist cleanup authorization in the same transaction as terminal task facts."""

import uuid


def cleanup_reason(row):
    if row["auto_mode"] == "abandoned":
        return "explicit_abandon"
    if row["locally_cancelled"]:
        return "local_cancel"
    if row["remote_state"] in ("failed", "cancelled"):
        return "remote_" + row["remote_state"]
    if row["remote_state"] == "succeeded" and row["delivery"] == "ready":
        return "artifacts_ready"
    return None


def enqueue_cleanup(connection, row):
    reason = cleanup_reason(row)
    if not reason:
        return
    for material in connection.execute(
        "SELECT material_id FROM material_copies m WHERE task_id=? AND state!='cleaned' "
        "AND NOT EXISTS (SELECT 1 FROM cleanup_jobs j WHERE j.material_id=m.material_id)",
        (row["task_id"],),
    ).fetchall():
        connection.execute(
            "INSERT INTO cleanup_jobs VALUES (?,?,?,0,'new',NULL,NULL)",
            (uuid.uuid4().hex, material[0], reason),
        )
