"""Isolated test dependencies; no provider credentials or public network access."""

import os
import socket
import threading
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


def pytest_configure(config):
    if config.option.basetemp is None:
        # A unique workspace-owned path avoids unrelated machine-wide pytest state.
        parent = config.rootpath / ".cache" / "test-runs"
        parent.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(parent / uuid.uuid4().hex)


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, tmp_path):
    for name in tuple(os.environ):
        if name.startswith("ZHENZHEN_SEEDANCE_") or name.upper() in {
            "API_KEY",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "NO_PROXY",
        }:
            monkeypatch.delenv(name)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local-app-data"))
    monkeypatch.chdir(tmp_path)

    # Isolate both new configuration sources, including inherited child processes.
    from zhenzhen_seedance_video import config as configuration

    install = tmp_path / "installation"
    install.mkdir()
    monkeypatch.setattr(configuration, "installation_root", lambda: install)
    monkeypatch.setattr(configuration, "_read_user_environment", lambda excluded: {})
    bootstrap = tmp_path / "bootstrap"
    bootstrap.mkdir()
    (bootstrap / "sitecustomize.py").write_text(
        "from pathlib import Path\n"
        "from zhenzhen_seedance_video import config\n"
        f"config.installation_root = lambda: Path({str(install)!r})\n"
        "config._read_user_environment = lambda excluded: {}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(bootstrap))


@pytest.fixture(autouse=True)
def network_guard(monkeypatch):
    """Permit only explicitly registered local fake-server ports."""
    ports = set()
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_getaddrinfo = socket.getaddrinfo
    original_socketpair = socket.socketpair
    internal = threading.local()

    def check(address):
        if not isinstance(address, tuple) or address[0] not in {"127.0.0.1", "::1"}:
            raise AssertionError("Test attempted non-local network access")
        if address[1] not in ports and not getattr(internal, "socketpair", False):
            raise AssertionError("Test attempted an unregistered local endpoint")

    def socketpair(*args, **kwargs):
        # Windows asyncio uses a stdlib loopback pair for internal wakeups.
        internal.socketpair = True
        try:
            return original_socketpair(*args, **kwargs)
        finally:
            internal.socketpair = False

    def connect(sock, address):
        check(address)
        return original_connect(sock, address)

    def connect_ex(sock, address):
        check(address)
        return original_connect_ex(sock, address)

    def getaddrinfo(host, port, *args, **kwargs):
        check((host, port))
        return original_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(socket, "socketpair", socketpair)
    return ports


@dataclass
class FakeClock:
    utc: float = 1_800_000_000.0
    monotonic: float = 0.0

    def advance(self, seconds):
        self.utc += seconds
        self.monotonic += seconds


@pytest.fixture
def clock():
    return FakeClock()


@dataclass
class Faults:
    pending: dict[str, Exception] = field(default_factory=dict)

    def hit(self, point):
        if error := self.pending.pop(point, None):
            raise error


@pytest.fixture
def faults():
    return Faults()


@dataclass
class FakeHTTP:
    responses: list[tuple[int, dict, bytes]] = field(default_factory=list)
    requests: list[tuple[str, str, bytes]] = field(default_factory=list)
    url: str = ""


@pytest.fixture
def fake_http(network_guard):
    state = FakeHTTP()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def respond(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            state.requests.append((self.command, self.path, body))
            status, headers, data = state.responses.pop(0) if state.responses else (500, {}, b"")
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_port
    network_guard.add(port)
    state.url = f"http://127.0.0.1:{port}"
    worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    worker.start()
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
        network_guard.remove(port)
        assert not worker.is_alive(), "Fake HTTP worker did not stop"
