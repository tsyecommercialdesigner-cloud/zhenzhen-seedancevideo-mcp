"""Verify the child-process guard before exercising synthetic providers."""

import subprocess
import sys


def test_child_blocks_external_dns_and_direct_ip():
    script = """
import socket
for operation in (
    lambda: socket.getaddrinfo('api.seedance.nz', 443),
    lambda: socket.socket().connect(('203.0.113.1', 443)),
):
    try:
        operation()
    except OSError as error:
        assert 'external network disabled' in str(error)
    else:
        raise AssertionError('external network guard was bypassed')
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
