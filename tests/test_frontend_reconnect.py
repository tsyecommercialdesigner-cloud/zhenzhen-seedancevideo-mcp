import asyncio

import pytest

from zhenzhen_seedance_video.frontend import ReconnectingClient


class FakeConnection:
    def __init__(self, closed=False, fail=False):
        self.writer = self
        self.receiver = self
        self.closed = closed
        self.fail = fail
        self.calls = 0

    def is_closing(self):
        return self.closed

    def done(self):
        return self.closed

    async def close(self):
        self.closed = True

    async def call(self, method, params, *, wait_seconds):
        self.calls += 1
        if self.fail:
            self.closed = True
            raise ConnectionError("lost after send")
        return method


async def test_dead_connection_reconnects_once_for_concurrent_calls():
    old = FakeConnection(closed=True)
    new = FakeConnection()
    connections = []

    async def connect():
        connections.append(1)
        await asyncio.sleep(0)
        return new

    proxy = ReconnectingClient(connect, old)
    assert await asyncio.gather(proxy.call("a"), proxy.call("b")) == ["a", "b"]
    assert len(connections) == 1
    await proxy.close()


async def test_failure_after_send_is_not_replayed():
    old = FakeConnection(fail=True)
    new = FakeConnection()

    async def connect():
        return new

    proxy = ReconnectingClient(connect, old)
    with pytest.raises(ConnectionError):
        await proxy.call("submit_video")
    assert old.calls == 1 and new.calls == 0
    assert await proxy.call("get_service_status") == "get_service_status"
    await proxy.close()
