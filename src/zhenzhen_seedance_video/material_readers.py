"""One shared per-database reader gate; cancellation must finish closing handles."""

import asyncio
import threading
from contextlib import asynccontextmanager

from .cleanup_rules import cleanup_reason


class MaterialReadError(RuntimeError):
    pass


class MaterialReaders:
    def __init__(self, database):
        self.db = database
        self.active = {}
        self.blocked = set()

    @asynccontextmanager
    async def use(self, task_id):
        current, stop = asyncio.current_task(), threading.Event()
        if task_id in self.blocked:
            raise MaterialReadError("MATERIAL_CLEANUP_PENDING")
        self.active.setdefault(task_id, {}).setdefault(current, []).append(stop)
        try:

            def check(c):
                row = c.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
                if (
                    row is None
                    or cleanup_reason(row)
                    or c.execute(
                        "SELECT 1 FROM cleanup_jobs j JOIN material_copies m USING(material_id) "
                        "WHERE m.task_id=?",
                        (task_id,),
                    ).fetchone()
                ):
                    raise MaterialReadError("MATERIAL_CLEANUP_PENDING")

            await self.db.execute(check, write=False)
            yield stop
        finally:
            self.active[task_id][current].remove(stop)
            if not self.active[task_id][current]:
                del self.active[task_id][current]
            if not self.active[task_id]:
                del self.active[task_id]

    async def quiesce(self, task_id, wait_seconds):
        self.blocked.add(task_id)
        readers = dict(self.active.get(task_id, {}))
        for task, signals in readers.items():
            for stop in signals:
                stop.set()
            task.cancel()
        if readers:
            _, pending = await asyncio.wait(readers, timeout=wait_seconds)
            if pending:
                raise RuntimeError("MATERIAL_READERS_BUSY")
            await asyncio.gather(*readers, return_exceptions=True)

    @staticmethod
    async def thread(function, *args, **kwargs):
        work = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
        try:
            return await asyncio.shield(work)
        except asyncio.CancelledError:
            await asyncio.gather(work, return_exceptions=True)
            raise


def material_readers(database):
    if not hasattr(database, "_material_readers"):
        database._material_readers = MaterialReaders(database)
    return database._material_readers
