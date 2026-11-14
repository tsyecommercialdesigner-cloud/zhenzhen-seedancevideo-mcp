import asyncio
from dataclasses import replace

import httpx2
import pytest

from zhenzhen_seedance_video.config import load_configuration
from zhenzhen_seedance_video.network import NetworkError, NetworkPolicy, bypass, origin


@pytest.fixture
def configuration(monkeypatch):
    monkeypatch.setenv("ZHENZHEN_SEEDANCE_API_KEY", "synthetic-secret")
    return load_configuration()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "phase,method", [("submit", "POST"), ("query", "GET"), ("upload", "POST"), ("download", "GET")]
)
async def test_real_local_bytes_all_phases(configuration, fake_http, monkeypatch, phase, method):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    policy = NetworkPolicy(configuration, _test_origins=[origin(fake_http.url)])
    fake_http.responses.append((200, {}, b"result"))
    try:
        assert await policy.request(method, fake_http.url, phase=phase, content=b"input") == (
            200,
            b"result",
        )
        assert fake_http.requests[0][2] == b"input"
    finally:
        await policy.close()
    assert all(c.is_closed for c in policy._clients.values())


@pytest.mark.asyncio
async def test_real_proxy_and_explicit_bypass(configuration, fake_http):
    # The fake server acts as an HTTP forward proxy and records absolute-form targets.
    target = "http://synthetic.invalid/video"
    policy = NetworkPolicy(
        replace(configuration, proxy_url=fake_http.url), _test_origins=[origin(target)]
    )
    fake_http.responses.append((200, {}, b"proxied"))
    try:
        assert await policy.request("GET", target, phase="download") == (200, b"proxied")
        assert fake_http.requests[0][1] == target
    finally:
        await policy.close()
    direct = NetworkPolicy(
        replace(configuration, proxy_url="http://127.0.0.1:1", proxy_bypass=("127.0.0.1",)),
        _test_origins=[origin(fake_http.url)],
    )
    fake_http.responses.append((200, {}, b"direct"))
    try:
        assert await direct.request("GET", fake_http.url, phase="query") == (200, b"direct")
    finally:
        await direct.close()


@pytest.mark.asyncio
async def test_redirect_auth_proxy_reselection_and_no_cookie(configuration):
    requests = []

    async def respond(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx2.Response(
                302,
                headers={"location": "https://cdn.example/video", "set-cookie": "session=private"},
                request=request,
            )
        return httpx2.Response(403, content=b"no", request=request)

    policy = NetworkPolicy(
        configuration,
        _test_origins=[origin("https://api.seedance.nz"), origin("https://cdn.example")],
        _transport=httpx2.MockTransport(respond),
    )
    try:
        assert await policy.request(
            "GET", "https://api.seedance.nz/task", phase="query", credential=True
        ) == (403, b"no")
        assert requests[0].headers["authorization"] == "Bearer synthetic-secret"
        assert "authorization" not in requests[1].headers and "cookie" not in requests[1].headers
        assert len(requests) == 2  # 403 must not cause an authenticated retry.
    finally:
        await policy.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "location,code",
    [
        ("http://cdn.example/x", "HTTPS_DOWNGRADE"),
        ("https://api.seedance.nz/x", "REDIRECT_LOOP"),
        ("https://127.0.0.1/x", "UNSAFE_NETWORK"),
    ],
)
async def test_unsafe_redirects(configuration, location, code):
    async def resolved(host, port):
        return ["127.0.0.1"]

    policy = NetworkPolicy(
        configuration,
        _test_origins=[origin("https://api.seedance.nz")],
        _resolver=resolved,
        _transport=httpx2.MockTransport(
            lambda r: httpx2.Response(302, headers={"location": location}, request=r)
        ),
    )
    try:
        with pytest.raises(NetworkError, match=code):
            await policy.request("GET", "https://api.seedance.nz/x", phase="query", credential=True)
    finally:
        await policy.close()


@pytest.mark.asyncio
async def test_non_idempotent_no_redirect_and_response_bound(configuration):
    transport = httpx2.MockTransport(
        lambda r: httpx2.Response(307, headers={"location": "/next"}, request=r)
    )
    policy = NetworkPolicy(
        configuration, _test_origins=[origin("https://api.seedance.nz")], _transport=transport
    )
    try:
        with pytest.raises(NetworkError, match="NON_IDEMPOTENT"):
            await policy.request(
                "POST",
                "https://api.seedance.nz/x",
                phase="submit",
                credential=True,
                json={"prompt": "private"},
            )
    finally:
        await policy.close()


@pytest.mark.asyncio
async def test_total_timeout_cancellation_and_resource_closure(configuration):
    entered = asyncio.Event()

    async def slow(request):
        entered.set()
        await asyncio.sleep(10)
        return httpx2.Response(200)

    config = replace(
        configuration, limits=dict(configuration.limits) | {"REQUEST_TIMEOUT_SECONDS": 0.05}
    )
    policy = NetworkPolicy(
        config,
        _test_origins=[origin("https://api.seedance.nz")],
        _transport=httpx2.MockTransport(slow),
    )
    try:
        with pytest.raises(NetworkError, match="NETWORK_TIMEOUT"):
            await policy.request("GET", "https://api.seedance.nz/x", phase="query")
        task = asyncio.create_task(
            policy.request("GET", "https://api.seedance.nz/x", phase="query")
        )
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        await policy.close()


def test_ca_failure_and_bypass(configuration, tmp_path):
    ca = tmp_path / "bad.pem"
    ca.write_text("not a certificate")
    with pytest.raises(NetworkError, match="INVALID_TRUSTED_CA"):
        NetworkPolicy(replace(configuration, ca_file=ca))
    assert bypass("x.example.com", (".example.com",))
    assert not bypass("badexample.com", (".example.com",))
    assert bypass("10.0.0.5", ("10.0.0.0/24",))
    assert not bypass("example.com", ("other.com",))


@pytest.mark.asyncio
async def test_dns_pin_and_tls_name(configuration):
    seen = []

    async def resolver(host, port):
        return ["8.8.8.8"]

    policy = NetworkPolicy(
        configuration,
        _resolver=resolver,
        _transport=httpx2.MockTransport(
            lambda r: seen.append(r) or httpx2.Response(200, content=b"ok")
        ),
    )
    try:
        await policy.request("GET", "https://cdn.example/video", phase="download")
        assert seen[0].url.host == "8.8.8.8"
        assert seen[0].headers["host"] == "cdn.example"
        assert seen[0].extensions["sni_hostname"] == "cdn.example"
    finally:
        await policy.close()


@pytest.mark.asyncio
async def test_real_tls_custom_ca_required(configuration, network_guard, tmp_path):
    import ipaddress
    import ssl
    import threading
    from datetime import UTC, datetime, timedelta
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(minutes=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp_path / "synthetic-ca.pem"
    key_path = tmp_path / "synthetic-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    network_guard.add(server.server_port)
    worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    worker.start()
    url = f"https://127.0.0.1:{server.server_port}/test"
    default = NetworkPolicy(configuration, _test_origins=[origin(url)])
    trusted = NetworkPolicy(replace(configuration, ca_file=cert_path), _test_origins=[origin(url)])
    try:
        with pytest.raises(NetworkError, match="NETWORK_REQUEST_FAILED"):
            await default.request("GET", url, phase="query")
        assert await trusted.request("GET", url, phase="download") == (200, b"ok")
        proxy_target = "http://synthetic.invalid/video"
        proxy_policy = NetworkPolicy(
            replace(
                configuration,
                proxy_url=url.rsplit("/", 1)[0],
                ca_file=cert_path,
            ),
            _test_origins=[origin(proxy_target)],
        )
        try:
            assert await proxy_policy.request("GET", proxy_target, phase="download") == (200, b"ok")
        finally:
            await proxy_policy.close()
    finally:
        await default.close()
        await trusted.close()
        server.shutdown()
        server.server_close()
        worker.join(3)
    assert not worker.is_alive()


@pytest.mark.asyncio
async def test_stream_idle_timeout_and_close(configuration):
    class SlowStream(httpx2.AsyncByteStream):
        closed = False

        async def __aiter__(self):
            yield b"first"
            raise httpx2.ReadTimeout("synthetic timeout with untrusted text")

        async def aclose(self):
            self.closed = True

    stream = SlowStream()
    policy = NetworkPolicy(
        configuration,
        _test_origins=[origin("https://cdn.example")],
        _transport=httpx2.MockTransport(lambda r: httpx2.Response(200, stream=stream)),
    )
    try:
        with pytest.raises(NetworkError, match="NETWORK_TIMEOUT"):
            await policy.request("GET", "https://cdn.example/x", phase="download")
        assert stream.closed
    finally:
        await policy.close()


@pytest.mark.asyncio
async def test_response_limit_and_redirect_limit(configuration):
    count = 0

    def redirect(request):
        nonlocal count
        count += 1
        return httpx2.Response(302, headers={"location": f"/hop-{count}"})

    policy = NetworkPolicy(
        configuration,
        _test_origins=[origin("https://cdn.example")],
        _transport=httpx2.MockTransport(redirect),
    )
    try:
        with pytest.raises(NetworkError, match="REDIRECT_LIMIT"):
            await policy.request("GET", "https://cdn.example/start", phase="download")
        assert count == 6
    finally:
        await policy.close()
    policy = NetworkPolicy(
        configuration,
        _test_origins=[origin("https://cdn.example")],
        _transport=httpx2.MockTransport(lambda r: httpx2.Response(200, content=b"oversize")),
    )
    try:
        with pytest.raises(NetworkError, match="RESPONSE_BYTES_LIMIT"):
            await policy.request("GET", "https://cdn.example/x", phase="query", limit=2)
    finally:
        await policy.close()


@pytest.mark.asyncio
async def test_proxy_selection_each_hop(configuration, fake_http):
    calls = []
    target = "https://api.seedance.nz/start"

    def respond(request):
        calls.append(request)
        return httpx2.Response(302, headers={"location": fake_http.url + "/end"})

    policy = NetworkPolicy(
        replace(configuration, proxy_url=fake_http.url, proxy_bypass=("127.0.0.1",)),
        _test_origins=[origin(target), origin(fake_http.url)],
        _transport=httpx2.MockTransport(respond),
    )
    # Selecting a different origin must rebuild the proxy decision, independent of auth state.
    first = policy._client(target, True)
    second = policy._client(fake_http.url, False)
    assert first is not second
    assert (fake_http.url, True, origin(target)) in policy._clients
    assert (None, False, origin(fake_http.url)) in policy._clients
    await policy.close()


@pytest.mark.asyncio
async def test_real_multipart_uses_same_policy(configuration, fake_http):
    policy = NetworkPolicy(configuration, _test_origins=[origin(fake_http.url)])
    fake_http.responses.append((200, {}, b"synthetic upload receipt"))
    try:
        await policy.request(
            "POST",
            fake_http.url,
            phase="upload",
            credential=True,
            files={"file": ("synthetic.mp4", b"fake-video-bytes", "video/mp4")},
        )
        assert b"fake-video-bytes" in fake_http.requests[0][2]
        assert b'name="file"' in fake_http.requests[0][2]
    finally:
        await policy.close()


@pytest.mark.asyncio
async def test_real_redirect_from_proxy_to_bypass(configuration, fake_http):
    first = "http://synthetic.invalid/start"
    fake_http.responses.extend(
        [(302, {"Location": fake_http.url + "/final"}, b""), (200, {}, b"final")]
    )
    policy = NetworkPolicy(
        replace(configuration, proxy_url=fake_http.url, proxy_bypass=("127.0.0.1",)),
        _test_origins=[origin(first), origin(fake_http.url)],
    )
    try:
        assert await policy.request("GET", first, phase="download") == (200, b"final")
        assert [r[1] for r in fake_http.requests] == [first, "/final"]
    finally:
        await policy.close()
