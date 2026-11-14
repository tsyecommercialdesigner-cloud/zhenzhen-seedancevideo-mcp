import asyncio
import json
import struct

import pytest

from zhenzhen_seedance_video.config import load_configuration
from zhenzhen_seedance_video.rpc import RPCServer, read_frame, write_frame


@pytest.fixture
async def rpc(tmp_path, network_guard):
    config = load_configuration(
        environ={"LOCALAPPDATA": str(tmp_path), "ZHENZHEN_SEEDANCE_API_KEY": "synthetic-secret"}
    )
    calls = []

    async def echo(params):
        calls.append(params)
        return params

    server = RPCServer(config, {"echo": echo}, frame_limit=4096, max_inflight=1, auth_timeout=0.2)
    port = await server.start()
    network_guard.add(port)
    try:
        yield server, calls
    finally:
        await server.close()
        network_guard.remove(port)


async def connect(server, **changes):
    reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
    await write_frame(writer, {"token": server.token, "protocol": 1} | changes, 4096)
    result = await asyncio.wait_for(read_frame(reader, 4096), 2)
    return reader, writer, result


async def shutdown(writer):
    writer.close()
    await writer.wait_closed()


async def test_authentication_precedes_dispatch_and_host_count(rpc):
    server, calls = rpc
    reader, writer, result = await connect(server, token="bad", method="echo", params={})
    assert result["error"] == "AUTHENTICATION_FAILED"
    assert calls == []
    assert len(server.authenticated) == 0
    await shutdown(writer)
    reader, writer, result = await connect(server)
    try:
        assert result["ok"]
        assert len(server.authenticated) == 1
        await write_frame(writer, {"id": "1", "method": "echo", "params": {"value": 42}}, 4096)
        assert (await read_frame(reader, 4096))["result"] == {"value": 42}
    finally:
        await shutdown(writer)


async def test_protocol_and_configuration_conflict_reject_new_client_only(rpc):
    server, calls = rpc
    existing_reader, existing_writer, _ = await connect(server)
    try:
        for changes, error in [
            ({"protocol": 999}, "PROTOCOL_INCOMPATIBLE"),
            (
                {"configuration": {"ZHENZHEN_SEEDANCE_API_KEY": "other-secret"}},
                "CONFIGURATION_CONFLICT",
            ),
        ]:
            _, writer, result = await connect(server, **changes)
            assert result["error"] == error
            assert "secret" not in json.dumps(result)
            await shutdown(writer)
        assert len(server.authenticated) == 1
        await write_frame(existing_writer, {"id": "existing", "method": "echo"}, 4096)
        assert (await read_frame(existing_reader, 4096))["ok"]
        assert calls == [{}]
    finally:
        await shutdown(existing_writer)


async def test_frame_size_invalid_json_and_auth_timeout(rpc):
    server, calls = rpc
    for body in (b'{"token":"a","token":"b"}', b"[]", b"not-json"):
        reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
        writer.write(struct.pack("!I", len(body)) + body)
        await writer.drain()
        assert (await read_frame(reader, 4096))["error"] == "INVALID_FRAME"
        await shutdown(writer)
    reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
    writer.write(struct.pack("!I", 4097))
    await writer.drain()
    assert (await read_frame(reader, 4096))["error"] == "FRAME_TOO_LARGE"
    await shutdown(writer)
    reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
    assert await asyncio.wait_for(reader.read(1), 2) == b""
    await shutdown(writer)
    assert calls == []


async def test_duplicate_and_inflight_limit(rpc):
    server, _ = rpc
    entered, release = asyncio.Event(), asyncio.Event()
    count = 0

    async def slow(params):
        nonlocal count
        count += 1
        entered.set()
        await release.wait()
        return "done"

    server.handlers["slow"] = slow
    reader, writer, _ = await connect(server)
    try:
        await write_frame(writer, {"id": "1", "method": "slow"}, 4096)
        await asyncio.wait_for(entered.wait(), 2)
        for identifier in ("1", "2"):
            await write_frame(writer, {"id": identifier, "method": "slow"}, 4096)
            assert (await read_frame(reader, 4096))["error"] == "REQUEST_CONFLICT_OR_LIMIT"
        release.set()
        assert (await read_frame(reader, 4096))["result"] == "done"
        assert count == 1
    finally:
        release.set()
        await shutdown(writer)


async def test_connection_cap_and_discovery_protection(rpc, tmp_path):
    server, _ = rpc
    server.max_connections = 1
    _, writer, _ = await connect(server)
    try:
        reader2, writer2 = await asyncio.open_connection("127.0.0.1", server.port)
        assert (await read_frame(reader2, 4096))["error"] == "CONNECTION_LIMIT"
        await shutdown(writer2)
        server.publish_discovery(tmp_path / "runtime")
        discovery = json.loads((tmp_path / "runtime/discovery.json").read_text())
        assert discovery["port"] == server.port
        assert server.token not in json.dumps(discovery)
        assert (tmp_path / "runtime/rpc-token").read_text() == server.token
        assert server._server.sockets[0].getsockname()[0] == "127.0.0.1"
    finally:
        await shutdown(writer)


async def test_server_close_releases_pending_transport_handlers(rpc):
    server, _ = rpc
    entered = asyncio.Event()

    async def waiting(params):
        entered.set()
        await asyncio.Event().wait()

    server.handlers["waiting"] = waiting
    _, writer, _ = await connect(server)
    await write_frame(writer, {"id": "waiting", "method": "waiting"}, 4096)
    await asyncio.wait_for(entered.wait(), 1)
    await asyncio.wait_for(server.close(), 1)
    assert not server.authenticated
    assert all(task.done() for task in server._operations)
    await shutdown(writer)


async def test_handshake_ignores_backend_file_edited_after_start(rpc, tmp_path):
    server, _ = rpc
    (tmp_path / "installation/.env").write_text(
        'ZHENZHEN_SEEDANCE_API_KEY="unterminated-private', encoding="utf-8"
    )
    reader, writer, result = await connect(server)
    try:
        assert result["ok"]
        _, rejected, conflict = await connect(
            server, configuration={"ZHENZHEN_SEEDANCE_API_KEY": "different-private"}
        )
        try:
            assert conflict["error"] == "CONFIGURATION_CONFLICT"
            assert "private" not in json.dumps(conflict)
        finally:
            await shutdown(rejected)
        await write_frame(writer, {"id": "still-alive", "method": "echo"}, 4096)
        assert (await read_frame(reader, 4096))["ok"]
    finally:
        await shutdown(writer)


def test_metadata_publication_retries_only_bounded_permission_errors(tmp_path, monkeypatch):
    from zhenzhen_seedance_video import rpc

    path = tmp_path / "discovery.json"
    path.write_bytes(b"old")
    original = rpc.os.replace
    attempts = []

    def retry(source, target):
        attempts.append(target)
        if len(attempts) < 3:
            raise PermissionError("reader still open")
        original(source, target)

    monkeypatch.setattr(rpc.os, "replace", retry)
    monkeypatch.setattr(rpc.time, "sleep", lambda _: None)
    rpc._publish(path, b"new")
    assert path.read_bytes() == b"new" and len(attempts) == 3
    attempts.clear()

    def denied(source, target):
        attempts.append(target)
        raise PermissionError("persistent denial")

    monkeypatch.setattr(rpc.os, "replace", denied)
    with pytest.raises(PermissionError):
        rpc._publish(path, b"rejected")
    assert len(attempts) == 10 and path.read_bytes() == b"new"
    assert not list(tmp_path.glob("*.tmp"))
