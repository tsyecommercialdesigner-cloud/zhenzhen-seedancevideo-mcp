"""Local draft facts are not a remote account or expiry verification API."""

import json

from .models import get_model
from .parameters import DraftFact


def local_draft_fact(connection, request, binding):
    metadata = request.get("metadata")
    if not isinstance(metadata, dict) or not isinstance(metadata.get("draft_task_id"), str):
        return None
    remote_id = metadata["draft_task_id"]
    rows = connection.execute(
        "SELECT model,effective_parameters,remote_state FROM tasks "
        "WHERE remote_id=? AND connection_binding=? LIMIT 2",
        (remote_id, binding),
    ).fetchall()
    if len(rows) != 1:
        return None
    row = rows[0]
    model = get_model(
        row["model"],
        api_id="zhenzhen-upscaler" if row["model"] == "zhenzhen-upscaler" else "seedance-video",
    )
    payload = json.loads(row["effective_parameters"])
    return DraftFact(
        remote_id=remote_id,
        region=model.region,
        is_draft=model.generation == "2.5" and payload.get("metadata", {}).get("draft") is True,
        completed=row["remote_state"] == "succeeded",
        same_account=None,
        valid=None,
    )
