"""Internal references can be useful without proving a complete artifact set."""

import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ArtifactManifest:
    references: list[dict] = field(repr=False)
    complete: bool = False


def completeness(connection, task_id):
    row = connection.execute(
        "SELECT details FROM task_events WHERE task_id=? "
        "AND kind='artifact_manifest_registered' ORDER BY event_id DESC LIMIT 1",
        (task_id,),
    ).fetchone()
    # Legacy registrations used the complete-set contract.
    return bool(json.loads(row[0])["complete"]) if row else True
