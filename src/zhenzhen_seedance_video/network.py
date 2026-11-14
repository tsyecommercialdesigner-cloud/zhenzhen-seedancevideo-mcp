"""Explicit shared network policy. No automatic submission retry or credential forwarding."""

import asyncio
import ipaddress
import socket
import ssl
from contextlib import asynccontextmanager
from urllib.parse import urljoin, urlsplit

import httpx2

from .models import BASE_URL


class NetworkError(RuntimeError):
    pass


def origin(url):
    try:
        if any(ord(char) <= 32 or ord(char) == 127 for char in str(url)):
            raise ValueError()
        parsed = urlsplit(str(url))
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            raise ValueError()
        return (
            parsed.scheme,
            parsed.hostname.lower(),
            parsed.port or (443 if parsed.scheme == "https" else 80),
        )
    except ValueError:
        raise NetworkError("INVALID_NETWORK_URL") from None


def bypass(host, rules):
    for rule in rules:
        try:
            if ipaddress.ip_address(host) in ipaddress.ip_network(rule, strict=False):
                return True
        except ValueError:
            if rule.startswith("."):
                if host == rule[1:] or host.endswith(rule):
                    return True
            elif host == rule:
                return True
    return False


async def resolve(host, port):
    records = await asyncio.to_thread(socket.getaddrinfo, host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(item[4][0] for item in records))


class NetworkPolicy:
    def __init__(self, configuration, *, _test_origins=(), _resolver=resolve, _transport=None):
        self.config = configuration
        self._test_origins = frozenset(_test_origins)
        self._resolve = _resolver
        self._transport = _transport
        self._clients = {}
        self._closed = False
        try:
            self.ssl_context = ssl.create_default_context()
            if configuration.ca_file:
                self.ssl_context.load_verify_locations(cafile=str(configuration.ca_file))
        except (OSError, ssl.SSLError):
            raise NetworkError("INVALID_TRUSTED_CA") from None

    def _client(self, url, credential):
        proxy = (
            self.config.proxy_url if not bypass(origin(url)[1], self.config.proxy_bypass) else None
        )
        key = (proxy, credential, origin(url))
        if key not in self._clients:
            if len(self._clients) >= 64:
                raise NetworkError("NETWORK_POOL_LIMIT")
            limit = (
                self.config.limits["QUERY_CONCURRENCY"]
                + self.config.limits["DOWNLOAD_CONCURRENCY"]
                + self.config.limits["UPLOAD_CONCURRENCY"]
                + self.config.limits["GENERATION_CONCURRENCY"]
            )
            self._clients[key] = httpx2.AsyncClient(
                verify=self.ssl_context,
                proxy=httpx2.Proxy(
                    proxy,
                    ssl_context=self.ssl_context if urlsplit(proxy).scheme == "https" else None,
                )
                if proxy
                else None,
                trust_env=False,
                follow_redirects=False,
                limits=httpx2.Limits(max_connections=limit, max_keepalive_connections=limit),
                timeout=httpx2.Timeout(
                    self.config.limits["REQUEST_TIMEOUT_SECONDS"],
                    connect=self.config.limits["CONNECT_TIMEOUT_SECONDS"],
                ),
                transport=self._transport,
            )
        return self._clients[key]

    async def _target(self, url):
        parsed_origin = origin(url)
        if parsed_origin in self._test_origins:
            return httpx2.URL(url), {}
        if parsed_origin[0] != "https":
            raise NetworkError("HTTPS_REQUIRED")
        try:
            addresses = await self._resolve(parsed_origin[1], parsed_origin[2])
        except OSError:
            raise NetworkError("NETWORK_DNS_FAILED") from None
        if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
            raise NetworkError("UNSAFE_NETWORK_TARGET")
        # Pin the validated IP, preserving the original TLS name and HTTP authority.
        # This also prevents a proxy from resolving the target to a different address.
        target = httpx2.URL(url)
        return target.copy_with(host=addresses[0]), {"sni_hostname": target.host}

    @asynccontextmanager
    async def stream(self, method, url, *, phase, credential=False, allow_redirects=True, **body):
        if self._closed:
            raise NetworkError("NETWORK_CLOSED")
        if phase not in ("submit", "query", "upload", "download"):
            raise NetworkError("INVALID_NETWORK_PHASE")
        if credential and (
            phase == "download" or origin(url) not in ({origin(BASE_URL)} | self._test_origins)
        ):
            raise NetworkError("API_CREDENTIAL_SCOPE_REJECTED")
        if set(body) - {"json", "content", "data", "files"}:
            raise NetworkError("NETWORK_ARGUMENT_REJECTED")
        seconds = self.config.limits[
            {"upload": "UPLOAD_TIMEOUT_SECONDS", "download": "DOWNLOAD_TIMEOUT_SECONDS"}.get(
                phase, "REQUEST_TIMEOUT_SECONDS"
            )
        ]
        initial = origin(url)
        seen = set()
        response = None
        try:
            async with asyncio.timeout(seconds):
                for _ in range(6):
                    if url in seen:
                        raise NetworkError("REDIRECT_LOOP")
                    seen.add(url)
                    target, extensions = await self._target(url)
                    authenticated = credential and origin(url) == initial
                    client = self._client(url, authenticated)
                    headers = {"Host": httpx2.URL(url).netloc.decode()}
                    if authenticated:
                        headers["Authorization"] = "Bearer " + self.config.api_key
                    request = client.build_request(
                        method, target, headers=headers, extensions=extensions, **body
                    )
                    request.headers.pop("cookie", None)
                    response = await client.send(request, stream=True)
                    if response.status_code not in (301, 302, 303, 307, 308):
                        yield response
                        return
                    if not allow_redirects:
                        raise NetworkError("REDIRECT_NOT_ALLOWED")
                    location = response.headers.get("location")
                    await response.aclose()
                    response = None
                    if method != "GET" or phase in ("submit", "upload"):
                        raise NetworkError("NON_IDEMPOTENT_REDIRECT_REJECTED")
                    if not location:
                        raise NetworkError("REDIRECT_LOCATION_MISSING")
                    next_url = urljoin(url, location)
                    if origin(url)[0] == "https" and origin(next_url)[0] != "https":
                        raise NetworkError("HTTPS_DOWNGRADE_REJECTED")
                    # Once a credential leaves its origin, never restore it later in the chain.
                    if origin(next_url) != initial:
                        credential = False
                    url = next_url
                raise NetworkError("REDIRECT_LIMIT")
        except (TimeoutError, httpx2.TimeoutException):
            raise NetworkError("NETWORK_TIMEOUT") from None
        except httpx2.HTTPError:
            raise NetworkError("NETWORK_REQUEST_FAILED") from None
        finally:
            if response is not None:
                await response.aclose()

    async def request(
        self,
        method,
        url,
        *,
        phase,
        credential=False,
        limit=2 * 1024 * 1024,
        allow_redirects=True,
        **body,
    ):
        async with self.stream(
            method, url, phase=phase, credential=credential, allow_redirects=allow_redirects, **body
        ) as response:
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > limit:
                    raise NetworkError("RESPONSE_BYTES_LIMIT")
            return response.status_code, bytes(data)

    async def close(self):
        self._closed = True
        await asyncio.gather(*(client.aclose() for client in self._clients.values()))
