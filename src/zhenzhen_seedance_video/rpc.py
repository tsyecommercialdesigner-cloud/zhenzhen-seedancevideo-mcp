"""Authenticated loopback-only framed JSON transport for local frontends."""

import asyncio
import hmac
import json
import os
import secrets
import struct
import time
import uuid
from pathlib import Path

from .config import ConfigurationConflict, ConfigurationError, accept_explicit_configuration
from .ownership import process_identity
from .windows_security import protect_directory, reject_reparse_path

PROTOCOL_VERSION = 1


class ProtocolError(ValueError):
    pass


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("INVALID_FRAME")
        result[key] = value
    return result


def _constant(value):
    raise ProtocolError("INVALID_FRAME")


async def read_frame(reader, limit):
    size = struct.unpack("!I", await reader.readexactly(4))[0]
    if size == 0 or size > limit:
        raise ProtocolError("FRAME_TOO_LARGE")
    raw = await reader.readexactly(size)
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise ProtocolError("INVALID_FRAME") from None
    if not isinstance(value, dict):
        raise ProtocolError("INVALID_FRAME")
    return value


async def write_frame(writer, value, limit):
    try:
        data = json.dumps(
            value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode()
    except (ValueError, TypeError, RecursionError):
        raise ProtocolError("INVALID_RESPONSE") from None
    if len(data) > limit:
        raise ProtocolError("RESPONSE_TOO_LARGE")
    writer.write(struct.pack("!I", len(data)) + data)
    await writer.drain()


def _publish(path, data):
    reject_reparse_path(path)
    temporary = path.with_name(uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Windows readers may briefly deny FILE_SHARE_DELETE on the old record.
        # Retry only atomic local metadata publication, never business effects.
        for attempt in range(10):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.01)
    finally:
        temporary.unlink(missing_ok=True)


class RPCServer:
    def __init__(
        self,
        configuration,
        handlers,
        *,
        frame_limit=8388608,
        max_connections=32,
        max_inflight=8,
        auth_timeout=5,
        leases=None,
    ):
        if frame_limit < 256 or min(max_connections, max_inflight, auth_timeout) <= 0:
            raise ValueError("INVALID_RPC_LIMIT")
        self.configuration = configuration
        self.handlers = dict(handlers)
        self.frame_limit = frame_limit
        self.max_connections = max_connections
        self.max_inflight = max_inflight
        self.auth_timeout = auth_timeout
        self.leases = leases
        self.token = secrets.token_hex(32)
        self.instance_id = str(uuid.uuid4())
        self.authenticated = set()
        self._writers = set()
        self._connections = set()
        self._operations = set()
        self._server = None

    def __repr__(self):
        return "RPCServer(<authenticated loopback>)"

    async def start(self):
        self._server = await asyncio.start_server(self._accept, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self.port

    def publish_discovery(self, runtime_directory: Path, *, launch_id=None):
        if self._server is None:
            raise ProtocolError("SERVER_NOT_STARTED")
        protect_directory(runtime_directory)
        identity = process_identity(os.getpid())
        _publish(runtime_directory / "rpc-token", self.token.encode("ascii"))
        _publish(
            runtime_directory / "discovery.json",
            json.dumps(
                {
                    "pid": identity.pid,
                    "created_at": identity.created_at,
                    "instance_id": self.instance_id,
                    "port": self.port,
                    "protocol": PROTOCOL_VERSION,
                    "launch_id": launch_id,
                }
            ).encode(),
        )

    async def _accept(self, reader, writer):
        task = asyncio.current_task()
        self._connections.add(task)
        pending = {}
        methods = {}
        write_lock = asyncio.Lock()

        async def send(value):
            async with write_lock:
                await write_frame(writer, value, self.frame_limit)

        async def dispatch(request):
            identifier = request["id"]
            try:
                handler = self.handlers.get(request["method"])
                if handler is None:
                    response = {"id": identifier, "ok": False, "error": "METHOD_NOT_SUPPORTED"}
                else:
                    result = await handler(request.get("params", {}))
                    response = {"id": identifier, "ok": True, "result": result}
                try:
                    await send(response)
                except ProtocolError:
                    await send({"id": identifier, "ok": False, "error": "RESPONSE_TOO_LARGE"})
            except (ConnectionError, OSError):
                pass
            except Exception:
                try:
                    await send({"id": identifier, "ok": False, "error": "INTERNAL_ERROR"})
                except (ConnectionError, OSError):
                    pass
            finally:
                pending.pop(identifier, None)
                methods.pop(identifier, None)

        try:
            if len(self._writers) >= self.max_connections:
                await send({"ok": False, "error": "CONNECTION_LIMIT"})
                return
            self._writers.add(writer)
            hello = await asyncio.wait_for(read_frame(reader, self.frame_limit), self.auth_timeout)
            token = hello.get("token")
            if (
                not isinstance(token, str)
                or not token.isascii()
                or not hmac.compare_digest(token.encode(), self.token.encode())
            ):
                await send({"ok": False, "error": "AUTHENTICATION_FAILED"})
                return
            if type(hello.get("protocol")) is not int or hello["protocol"] != PROTOCOL_VERSION:
                await send({"ok": False, "error": "PROTOCOL_INCOMPATIBLE"})
                return
            explicit = hello.get("configuration", {})
            if not isinstance(explicit, dict) or any(
                not isinstance(v, str) for v in explicit.values()
            ):
                raise ProtocolError("INVALID_CONFIGURATION")
            if any(not key.startswith("ZHENZHEN_SEEDANCE_") for key in explicit):
                raise ProtocolError("INVALID_CONFIGURATION")
            try:
                accept_explicit_configuration(
                    self.configuration,
                    self.configuration.root,
                    {
                        key.removeprefix("ZHENZHEN_SEEDANCE_"): value
                        for key, value in explicit.items()
                    },
                )
            except ConfigurationConflict as error:
                await send({"ok": False, "error": "CONFIGURATION_CONFLICT", "fields": error.names})
                return
            except ConfigurationError:
                await send({"ok": False, "error": "INVALID_CONFIGURATION"})
                return
            if self.leases is not None and not self.leases.join(writer):
                await send({"ok": False, "error": "BACKEND_DRAINING"})
                return
            self.authenticated.add(writer)
            await send(
                {
                    "ok": True,
                    "protocol": PROTOCOL_VERSION,
                    "instance_id": self.instance_id,
                    "heartbeat_seconds": self.configuration.limits["HEARTBEAT_SECONDS"],
                }
            )
            while True:
                request = await read_frame(reader, self.frame_limit)
                if self.leases is not None and not self.leases.touch(writer):
                    raise ProtocolError("LEASE_EXPIRED")
                identifier = request.get("id")
                method = request.get("method")
                if (
                    not isinstance(identifier, str)
                    or not 1 <= len(identifier) <= 128
                    or not isinstance(method, str)
                    or not 1 <= len(method) <= 64
                    or not isinstance(request.get("params", {}), dict)
                ):
                    raise ProtocolError("INVALID_REQUEST")
                if identifier in pending or len(pending) >= self.max_inflight:
                    await send(
                        {"id": identifier, "ok": False, "error": "REQUEST_CONFLICT_OR_LIMIT"}
                    )
                    continue
                if method == "_cancel":
                    target = request.get("params", {}).get("request_id")
                    if isinstance(target, str) and methods.get(target) in {
                        "wait_task",
                        "copy_artifact",
                    }:
                        operation = pending.get(target)
                        if operation is not None:
                            operation.cancel()
                    await send({"id": identifier, "ok": True, "result": {"acknowledged": True}})
                    continue
                if method == "_heartbeat":
                    await send({"id": identifier, "ok": True, "result": {"alive": True}})
                    continue
                operation = asyncio.create_task(dispatch(request))
                pending[identifier] = operation
                methods[identifier] = method
                self._operations.add(operation)
                operation.add_done_callback(self._operations.discard)
        except (asyncio.IncompleteReadError, ConnectionError, OSError, TimeoutError):
            pass
        except ProtocolError as error:
            try:
                await send({"ok": False, "error": str(error)})
            except (ConnectionError, OSError):
                pass
        finally:
            if self.leases is not None:
                self.leases.drop(writer)
            self.authenticated.discard(writer)
            self._writers.discard(writer)
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass
            # Disconnect does not cancel already accepted business operations.
            if pending:
                await asyncio.gather(*list(pending.values()), return_exceptions=True)
            self._connections.discard(task)

    async def close(self):
        if self._server:
            self._server.close()
        for writer in list(self._writers):
            writer.close()
        for operation in list(self._operations):
            operation.cancel()
        for task in list(self._connections):
            task.cancel()
        await asyncio.gather(*list(self._connections), return_exceptions=True)
        await asyncio.gather(*list(self._operations), return_exceptions=True)
        if self._server:
            await self._server.wait_closed()
