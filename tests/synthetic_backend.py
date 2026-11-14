"""Test-only child process; excluded from every distribution."""

import asyncio
import json
import os
import sys
from pathlib import Path

from zhenzhen_seedance_video import runtime
from zhenzhen_seedance_video.artifacts import ArtifactService
from zhenzhen_seedance_video.network import NetworkPolicy, origin
from zhenzhen_seedance_video.provider import Capabilities
from zhenzhen_seedance_video.provider_response import Observation
from zhenzhen_seedance_video.task_state import TaskState

control = Path(sys.argv[1])
url = sys.argv[2]
phase = sys.argv[3]


def crash(point):
    if phase == point and not (control / "crashed").exists():
        (control / "crashed").write_text(point)
        os._exit(91)


class Adapter:
    capabilities = Capabilities()

    def __init__(self, db, config):
        self.db = db

    async def prepare(self, row):
        crash("prepare")
        return {}

    async def submit(self, row, payload):
        with (control / "posts.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"task_id": row["task_id"]}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        crash("submitted")
        return Observation(
            "synthetic-" + row["task_id"], row["model"], "queued", 0, None, None, None
        )

    async def query(self, row):
        if phase == "storage" and not (control / "fault").exists():
            self.db._fault.set()
            (control / "fault").touch()
            while not (control / "repair").exists():  # noqa: ASYNC110 -- cross-process file gate
                await asyncio.sleep(0.02)
            await self.db.reconcile(lambda c: None)
        status = "completed" if (control / "complete").exists() else "in_progress"
        return Observation(
            row["remote_id"],
            row["model"],
            status,
            100 if status == "completed" else 50,
            url + "/video" if status == "completed" else None,
            None,
            None,
        )

    async def artifacts(self, row):
        return [{"url": url + "/video"}]


original = TaskState.observe


async def observe(self, *args, **kwargs):
    result = await original(self, *args, **kwargs)
    crash("after_id")
    return result


TaskState.observe = observe


class Artifacts(ArtifactService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, hook=crash)


runtime.ArtifactService = Artifacts
asyncio.run(
    runtime.run_backend(
        adapter_factory=Adapter,
        network_factory=lambda config: NetworkPolicy(config, _test_origins=[origin(url)]),
    )
)
