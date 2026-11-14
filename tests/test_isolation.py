import os
import socket

import httpx2
import pytest


def test_environment_is_isolated(tmp_path):
    assert os.environ["LOCALAPPDATA"] == str(tmp_path / "local-app-data")
    assert "ZHENZHEN_SEEDANCE_API_KEY" not in os.environ


def test_public_network_is_blocked():
    with pytest.raises(AssertionError, match="non-local"):
        socket.create_connection(("api.seedance.nz", 443), timeout=1)


async def test_real_async_http_bytes_to_registered_fake(fake_http):
    fake_http.responses.append((200, {"Content-Type": "application/json"}, b'{"synthetic":true}'))
    async with httpx2.AsyncClient(trust_env=False) as client:
        response = await client.post(fake_http.url + "/synthetic", content=b"test-body")
    assert response.json() == {"synthetic": True}
    assert fake_http.requests == [("POST", "/synthetic", b"test-body")]


def test_clock_and_fault_injection(clock, faults):
    clock.advance(60)
    assert clock.monotonic == 60
    assert clock.utc == 1_800_000_060
    faults.pending["before_commit"] = OSError("synthetic disk error")
    with pytest.raises(OSError, match="synthetic"):
        faults.hit("before_commit")
    faults.hit("before_commit")
