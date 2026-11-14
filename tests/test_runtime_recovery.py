import asyncio

from zhenzhen_seedance_video.config import load_configuration
from zhenzhen_seedance_video.leases import LeaseManager
from zhenzhen_seedance_video.rpc import RPCServer, read_frame, write_frame
from zhenzhen_seedance_video.runtime import serve_until_idle


async def test_draining_rejects_rejoin_and_ends_inflight_with_bound(tmp_path, network_guard):
    config = load_configuration(
        environ={"LOCALAPPDATA": str(tmp_path), "ZHENZHEN_SEEDANCE_API_KEY": "synthetic"}
    )
    leases = LeaseManager(lease_seconds=1, grace_seconds=0.1, drain_seconds=0.2)
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def slow(params):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    server = RPCServer(config, {"slow": slow}, leases=leases)
    port = await server.start()
    network_guard.add(port)

    async def connection():
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        await write_frame(writer, {"protocol": 1, "token": server.token}, 8388608)
        return reader, writer, await read_frame(reader, 8388608)

    try:
        _, writer, hello = await connection()
        assert hello["ok"]
        await write_frame(writer, {"id": "slow", "method": "slow"}, 8388608)
        await asyncio.wait_for(started.wait(), 1)
        writer.close()
        await writer.wait_closed()
        loop = asyncio.create_task(serve_until_idle(server, leases))
        for _ in range(100):
            if not leases.network_allowed:
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("Backend did not start draining")
        assert not leases.dispatch_allowed
        _, rejected, response = await connection()
        assert response["error"] == "BACKEND_DRAINING"
        rejected.close()
        await rejected.wait_closed()
        await asyncio.wait_for(loop, 1)
        await asyncio.wait_for(server.close(), 1)
        assert cancelled.is_set()
    finally:
        await server.close()
        network_guard.remove(port)
