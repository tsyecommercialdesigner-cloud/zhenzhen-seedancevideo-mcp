"""Hidden per-user backend and authenticated frontend connection lifecycle."""

import asyncio
import contextlib
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

import pywintypes
import win32api
import win32con
import win32job
import win32process

from .admission import AdmissionService
from .artifacts import ArtifactService
from .cleanup import CleanupService
from .config import _read_configuration_sources, load_configuration
from .diagnostics import Diagnostics
from .leases import LeaseManager
from .lifecycle import Lifecycle
from .models import BASE_URL
from .network import NetworkPolicy
from .ownership import (
    OwnershipError,
    ProcessIdentity,
    StableLock,
    acquire_ownership,
    confirm_exited,
)
from .rpc import RPCServer, _publish, read_frame, write_frame
from .scheduler import Scheduler
from .storage import Database
from .tools import Tools
from .windows_security import CredentialBindings, protect_directory, reject_reparse_path


class RuntimeErrorCode(RuntimeError):
    pass


def read_record(path):
    reject_reparse_path(path)
    if not path.exists():
        return None
    try:
        if path.stat().st_size > 4096:
            raise ValueError()
        value = json.loads(path.read_bytes())
        if (
            type(value["pid"]) is not int
            or value["pid"] <= 0
            or not isinstance(value["created_at"], str)
        ):
            raise ValueError()
        return value
    except (OSError, ValueError, KeyError, TypeError):
        raise RuntimeErrorCode("INVALID_DISCOVERY_RECORD") from None


def identity(record):
    return ProcessIdentity(record["pid"], record["created_at"])


def launch_hidden(runtime_directory):
    """Called with startup lock held. No shell, inherited handles or key argv."""
    executable = str(Path(sys.executable).resolve())
    command = subprocess.list2cmdline([executable, "-m", "zhenzhen_seedance_video", "backend"])
    flags = win32con.CREATE_SUSPENDED | win32con.CREATE_NO_WINDOW
    if win32job.IsProcessInJob(win32api.GetCurrentProcess(), None):
        flags |= win32process.CREATE_BREAKAWAY_FROM_JOB
    startup = win32process.STARTUPINFO()
    startup.dwFlags |= win32con.STARTF_USESHOWWINDOW
    startup.wShowWindow = win32con.SW_HIDE
    launch_id = secrets.token_hex(16)
    environment = dict(os.environ) | {"ZHENZHEN_BACKEND_LAUNCH_ID": launch_id}
    try:
        process, thread, pid, _ = win32process.CreateProcess(
            executable,
            command,
            None,
            None,
            False,
            flags,
            environment,
            str(Path(__file__).resolve().parent),
            startup,
        )
    except pywintypes.error:
        raise RuntimeErrorCode("BACKEND_LAUNCH_OR_JOB_INCOMPATIBLE") from None
    try:
        record = {
            "pid": pid,
            "created_at": win32process.GetProcessTimes(process)["CreationTime"].isoformat(),
        }
        record["launch_id"] = launch_id
        try:
            _publish(runtime_directory / "starting.json", json.dumps(record).encode())
        except BaseException:
            # This new process is still suspended and has never opened the database.
            win32process.TerminateProcess(process, 2)
            raise
        win32process.ResumeThread(thread)
        return record
    finally:
        thread.Close()
        process.Close()


class BackendClient:
    def __init__(self, reader, writer, hello, heartbeat_seconds):
        self.reader, self.writer = reader, writer
        self.instance_id = hello["instance_id"]
        self.pending = {}
        self.sequence = 0
        self.lock = asyncio.Lock()
        self.receiver = asyncio.create_task(self._receive())
        self.heartbeat = asyncio.create_task(self._heartbeat(heartbeat_seconds))

    async def _receive(self):
        try:
            while True:
                response = await read_frame(self.reader, 8388608)
                future = self.pending.pop(response.get("id"), None)
                if future is not None and not future.done():
                    future.set_result(response)
        except (Exception, asyncio.CancelledError):
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(RuntimeErrorCode("BACKEND_CONNECTION_LOST"))
            self.pending.clear()

    async def _heartbeat(self, interval):
        try:
            while True:
                await asyncio.sleep(interval)
                await self.call("_heartbeat", {}, wait_seconds=max(1, interval))
        except (Exception, asyncio.CancelledError):
            self.writer.close()

    async def call(self, method, params=None, *, wait_seconds=30):
        self.sequence += 1
        identifier = str(self.sequence)
        future = asyncio.get_running_loop().create_future()
        self.pending[identifier] = future
        try:
            async with self.lock:
                await write_frame(
                    self.writer,
                    {"id": identifier, "method": method, "params": params or {}},
                    8388608,
                )
            response = await asyncio.wait_for(future, wait_seconds)
            if not response.get("ok"):
                raise RuntimeErrorCode(response.get("error", "RPC_FAILED"))
            return response["result"]
        except (asyncio.CancelledError, TimeoutError):
            if method in {"wait_task", "copy_artifact"}:

                async def cancel():
                    async with self.lock:
                        await write_frame(
                            self.writer,
                            {
                                "id": "cancel-" + identifier,
                                "method": "_cancel",
                                "params": {"request_id": identifier},
                            },
                            8388608,
                        )

                with contextlib.suppress(Exception):
                    await asyncio.shield(cancel())
            raise
        finally:
            self.pending.pop(identifier, None)

    async def close(self):
        self.heartbeat.cancel()
        self.writer.close()
        with contextlib.suppress(OSError):
            await self.writer.wait_closed()
        self.receiver.cancel()
        await asyncio.gather(self.heartbeat, self.receiver, return_exceptions=True)


async def _connect(runtime_directory, record, explicit):
    port = record.get("port")
    if type(port) is not int or not 1 <= port <= 65535:
        raise RuntimeErrorCode("INVALID_DISCOVERY_RECORD")
    token_path = runtime_directory / "rpc-token"
    reject_reparse_path(token_path)
    token = token_path.read_text(encoding="ascii")
    reader, writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), 2)
    try:
        await write_frame(
            writer,
            {
                "protocol": 1,
                "token": token,
                "configuration": {"ZHENZHEN_SEEDANCE_" + k: v for k, v in explicit.items()},
            },
            8388608,
        )
        hello = await asyncio.wait_for(read_frame(reader, 8388608), 5)
        if not hello.get("ok"):
            raise RuntimeErrorCode(hello.get("error", "HANDSHAKE_FAILED"))
        if hello.get("instance_id") != record.get("instance_id"):
            raise RuntimeErrorCode("BACKEND_IDENTITY_MISMATCH")
        # Backend reports its effective interval, so unspecified clients adopt it.
        return BackendClient(reader, writer, hello, hello.get("heartbeat_seconds", 5))
    except BaseException:
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()
        raise


async def connect_or_start(*, startup_timeout=30):
    root, explicit, _ = _read_configuration_sources()
    runtime_directory = root / "runtime"
    protect_directory(runtime_directory)
    deadline = time.monotonic() + startup_timeout
    lock = StableLock(runtime_directory, "startup.lock")
    while True:
        try:
            lock.acquire()
            break
        except OwnershipError as error:
            if str(error) != "LOCK_BUSY" or time.monotonic() >= deadline:
                raise
            await asyncio.sleep(0.05)
    try:
        record = read_record(runtime_directory / "discovery.json")
        if record is not None:
            try:
                return await _connect(runtime_directory, record, explicit)
            except (OSError, TimeoutError, RuntimeErrorCode) as error:
                if isinstance(error, RuntimeErrorCode) and str(error) not in ("BACKEND_DRAINING",):
                    raise
                # A live unresponsive process cannot be replaced.
                if str(error) != "BACKEND_DRAINING":
                    confirm_exited(identity(record))
                else:
                    while time.monotonic() < deadline:
                        try:
                            confirm_exited(identity(record))
                            break
                        except OwnershipError as waiting:
                            if str(waiting) != "OLD_PROCESS_STILL_ALIVE":
                                raise
                            await asyncio.sleep(0.05)
                    else:
                        raise RuntimeErrorCode("STARTUP_TIMEOUT")
        starting = read_record(runtime_directory / "starting.json")
        if starting is not None:
            confirm_exited(identity(starting))
        # Refuse to spawn if an undiscovered owner still holds the lock.
        with StableLock(runtime_directory, "owner.lock"):
            load_configuration()  # First startup needs complete valid configuration.
        launched = launch_hidden(runtime_directory)
        while time.monotonic() < deadline:
            record = read_record(runtime_directory / "discovery.json")
            if record is not None and record.get("launch_id") == launched["launch_id"]:
                try:
                    return await _connect(runtime_directory, record, explicit)
                except (OSError, TimeoutError):
                    pass
            await asyncio.sleep(0.05)
        raise RuntimeErrorCode("STARTUP_TIMEOUT")
    finally:
        lock.close()


async def run_backend(*, adapter_factory=None, network_factory=NetworkPolicy, upload_factory=None):
    configuration = load_configuration()
    directory = configuration.root / "runtime"
    previous = read_record(directory / "discovery.json")
    owner = acquire_ownership(directory, identity(previous) if previous else None)
    database = None
    server = None
    admission = None
    network = None
    cleanup = None
    artifacts = None
    diagnostics = None
    lifecycle = None
    background = None
    try:
        network = network_factory(configuration)
        database = await asyncio.to_thread(Database, configuration.state_dir)

        default_provider = adapter_factory is None and configuration.execution_mode == "provider"
        if adapter_factory is None and not default_provider:
            from .production import LocalNetwork

            network = LocalNetwork(network)

        bindings = CredentialBindings(configuration.root / "credentials")
        binding = bindings.bind(api_key=configuration.api_key, endpoint=BASE_URL)
        admission = AdmissionService(database, configuration, binding)
        cleanup = CleanupService(database, configuration)
        leases = LeaseManager(
            lease_seconds=configuration.limits["LEASE_TIMEOUT_SECONDS"],
            grace_seconds=configuration.limits["SHUTDOWN_GRACE_SECONDS"],
            drain_seconds=configuration.limits["SHUTDOWN_DRAIN_SECONDS"],
        )

        artifacts = ArtifactService(database, configuration, network)
        diagnostics = Diagnostics(
            configuration.root / "diagnostics", secrets=(configuration.api_key,)
        )
        scheduler = None
        if default_provider:
            from .production import ProductionAdapter, ProductionUploads, quarantine_unapproved

            await quarantine_unapproved(database)

            def adapter_factory(db, config):
                return ProductionAdapter(network, db)

            upload_factory = ProductionUploads
        if adapter_factory is not None:
            scheduler = Scheduler(
                database,
                configuration,
                binding,
                adapter_factory(database, configuration),
                leases=leases,
                delivery=artifacts,
                uploads=upload_factory(database, configuration, binding, network)
                if upload_factory is not None
                else None,
            )
        lifecycle = Lifecycle(admission, artifacts, cleanup, binding, leases, scheduler)
        await lifecycle.recover()
        # Startup recovery time is not time spent waiting for the first Host.
        leases.empty_since = leases.clock()
        facade = Tools(
            admission,
            artifacts,
            cleanup,
            scheduler=scheduler,
            leases=leases,
            diagnostics=diagnostics,
        )
        server = RPCServer(
            configuration,
            facade.handlers(),
            leases=leases,
            frame_limit=configuration.limits["RPC_FRAME_BYTES_LIMIT"],
        )
        await server.start()
        server.publish_discovery(directory, launch_id=os.environ.get("ZHENZHEN_BACKEND_LAUNCH_ID"))
        background = asyncio.create_task(lifecycle.run())
        serving = asyncio.create_task(serve_until_idle(server, leases, lifecycle))
        try:
            done, _ = await asyncio.wait((serving, background), return_when=asyncio.FIRST_COMPLETED)
            for completed in done:
                completed.result()
        finally:
            serving.cancel()
            await asyncio.gather(serving, return_exceptions=True)
    finally:
        if server:
            await server.close()
        if background:
            background.cancel()
            await asyncio.gather(background, return_exceptions=True)
        if lifecycle:
            await lifecycle.close()
        if cleanup:
            await cleanup.close()
        if artifacts:
            await artifacts.close()
        if diagnostics:
            diagnostics.close()
        if admission:
            await admission.close()
        if database:
            await database.close()
        if network:
            await network.close()
        owner.close()


async def serve_until_idle(server, leases, lifecycle=None):
    while True:
        for writer in leases.tick():
            writer.close()
        if not leases.network_allowed and (
            (not server._operations and (lifecycle is None or lifecycle.idle))
            or leases.drain_expired
        ):
            return
        await asyncio.sleep(0.05)
