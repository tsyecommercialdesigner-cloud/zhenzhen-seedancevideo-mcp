"""Default production composition: explicit installation and per-task authorization."""

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from .compatibility_adapter import CompatibilityAdapter
from .network import NetworkError
from .provider import ProviderFailure
from .task_state import _change
from .upload_service import UploadService

CODE = "PROVIDER_EXECUTION_NOT_AUTHORIZED"


def authorized(connection, task_id):
    record = connection.execute(
        "SELECT details FROM task_events WHERE task_id=? AND kind='accepted'",
        (task_id,),
    ).fetchone()
    return bool(record and json.loads(record[0]).get("provider_execution_authorized") is True)


async def require_authorized(database, task_id):
    if not await database.execute(lambda c: authorized(c, task_id), write=False):
        raise ProviderFailure(CODE)


async def quarantine_unapproved(database):
    def apply(connection):
        for record in connection.execute("SELECT * FROM tasks WHERE auto_mode='active'").fetchall():
            row = dict(record)
            if (
                row["stage"] == "settled"
                or row["locally_cancelled"]
                or authorized(connection, row["task_id"])
            ):
                continue
            reasons = set(json.loads(row["attention"])) | {CODE}
            _change(
                connection,
                row,
                {"auto_mode": "needs_attention", "attention": json.dumps(sorted(reasons))},
                kind="provider_execution_blocked",
                now=datetime.now(UTC).isoformat(),
            )

    await database.execute(apply)


class ProductionAdapter(CompatibilityAdapter):
    async def prepare(self, row):
        await require_authorized(self.db, row["task_id"])
        return await super().prepare(row)

    async def submit(self, row, payload):
        await require_authorized(self.db, row["task_id"])
        return await super().submit(row, payload)

    async def query(self, row):
        await require_authorized(self.db, row["task_id"])
        return await super().query(row)

    async def artifacts(self, row):
        await require_authorized(self.db, row["task_id"])
        return await super().artifacts(row)


class ProductionUploads(UploadService):
    async def prepare(self, row):
        await require_authorized(self.db, row["task_id"])
        return await super().prepare(row)


class LocalNetwork:
    def __init__(self, network):
        self.network = network

    async def request(self, *args, **kwargs):
        raise NetworkError("PROVIDER_EXECUTION_DISABLED")

    @asynccontextmanager
    async def stream(self, *args, **kwargs):
        raise NetworkError("PROVIDER_EXECUTION_DISABLED")
        yield  # pragma: no cover

    async def close(self):
        await self.network.close()
