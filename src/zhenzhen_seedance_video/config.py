"""Immutable per-backend configuration; never search a Host's working directory."""

import hmac
import ipaddress
import os
import sys
import tomllib
import winreg
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from urllib.parse import urlsplit

from dotenv.parser import parse_stream

PREFIX = "ZHENZHEN_SEEDANCE_"
INT_DEFAULTS = MappingProxyType(
    {
        "GENERATION_CONCURRENCY": 3,
        "QUERY_CONCURRENCY": 4,
        "DOWNLOAD_CONCURRENCY": 2,
        "UPLOAD_CONCURRENCY": 2,
        "ADMISSION_CONCURRENCY": 2,
        "CLEANUP_CONCURRENCY": 1,
        "QUEUE_LIMIT": 100,
        "INPUT_BYTES_LIMIT": 536870912,
        "CONNECT_TIMEOUT_SECONDS": 10,
        "REQUEST_TIMEOUT_SECONDS": 60,
        "UPLOAD_TIMEOUT_SECONDS": 300,
        "DOWNLOAD_TIMEOUT_SECONDS": 1800,
        "TRACKING_TIMEOUT_SECONDS": 21600,
        "POLL_INTERVAL_SECONDS": 5,
        "QUERY_RETRIES": 5,
        "UPLOAD_RETRIES": 3,
        "DOWNLOAD_RETRIES": 3,
        "CLEANUP_RETRIES": 3,
        "SHUTDOWN_GRACE_SECONDS": 10,
        "SHUTDOWN_DRAIN_SECONDS": 15,
        "STARTUP_TIMEOUT_SECONDS": 30,
        "HEARTBEAT_SECONDS": 5,
        "LEASE_TIMEOUT_SECONDS": 20,
        "WAIT_DEFAULT_SECONDS": 20,
        "WAIT_MAX_SECONDS": 30,
        "PAGE_DEFAULT_SIZE": 20,
        "PAGE_MAX_SIZE": 100,
        "TOOL_RESPONSE_BYTES_LIMIT": 32768,
        "ERROR_SUMMARY_CHARS_LIMIT": 512,
        "DIAGNOSTIC_BYTES_LIMIT": 8192,
        "HTTP_RESPONSE_BYTES_LIMIT": 2097152,
        "RPC_FRAME_BYTES_LIMIT": 8388608,
        "LOG_BYTES_LIMIT": 10485760,
        "LOG_BACKUP_COUNT": 5,
        "STREAM_IDLE_TIMEOUT_SECONDS": 60,
    }
)
STRING_FIELDS = frozenset(
    {"API_KEY", "OUTPUT_DIR", "PROXY_URL", "PROXY_BYPASS", "CA_FILE", "EXECUTION_MODE"}
)
OPTIONAL_INTS = frozenset({"DOWNLOAD_BYTES_LIMIT"})


class ConfigurationError(ValueError):
    """Contains only the setting name and a static reason, never the supplied value."""

    def __init__(self, name: str, reason: str):
        self.name = PREFIX + name
        self.reason = reason
        super().__init__(f"CONFIG_INVALID: {self.name}: {reason}")


@dataclass(frozen=True)
class Configuration:
    root: Path
    output_dir: Path
    api_key: str = field(repr=False)
    proxy_url: str | None = field(repr=False)
    proxy_bypass: tuple[str, ...]
    ca_file: Path | None
    limits: Mapping[str, int | None]
    sources: Mapping[str, str]
    explicit: frozenset[str]
    execution_mode: str = "local"

    @property
    def state_dir(self) -> Path:
        return self.root / "state"


def _absolute_local_path(raw: str, name: str) -> Path:
    path = Path(raw)
    if not path.is_absolute() or str(path).startswith(("\\\\", "//")):
        raise ConfigurationError(name, "requires an absolute local path")
    if ":" in str(path)[len(path.drive) :]:
        raise ConfigurationError(name, "alternate streams are not allowed")
    return path.resolve()


def _validate_bypass(raw: str) -> tuple[str, ...]:
    entries = tuple(item.strip().lower() for item in raw.split(","))
    for entry in entries:
        try:
            ipaddress.ip_network(entry, strict=False)
            continue
        except ValueError:
            pass
        domain = entry.removeprefix(".")
        if (
            not domain
            or any(c in domain for c in "/:@* \\")
            or any(
                not label or not all(c.isalnum() or c == "-" for c in label)
                for label in domain.split(".")
            )
        ):
            raise ConfigurationError("PROXY_BYPASS", "invalid domain, IP or CIDR entry")
    return entries


def installation_root() -> Path:
    """Resolve only known source / Windows virtualenv layouts, never cwd."""
    module = Path(__file__).resolve()
    source_root = module.parent.parent.parent
    if module.parent.parent.name == "src":
        try:
            with (source_root / "pyproject.toml").open("rb") as stream:
                project = tomllib.load(stream)
            if project.get("project", {}).get("name") == "zhenzhen-seedancevideo-mcp":
                return source_root
        except (OSError, ValueError):
            pass
    prefix = Path(sys.prefix).resolve()
    if (
        module.parent.parent == prefix / "Lib" / "site-packages"
        and (prefix / "pyvenv.cfg").is_file()
    ):
        # Project-local .venv belongs to its parent; a standalone venv is itself
        # the installation. Global Python installations are deliberately rejected.
        return prefix.parent if prefix.name == ".venv" else prefix
    raise ConfigurationError("INSTALL_DIRECTORY", "cannot identify service installation")


def _read_dotenv(path: Path) -> dict[str, str | None]:
    values = {}
    try:
        with path.open(encoding="utf-8-sig") as stream:
            for binding in parse_stream(stream):
                if binding.error:
                    raise ConfigurationError("ENV_FILE", "invalid configuration syntax")
                if binding.key is None:
                    continue
                key = binding.key.upper()
                if key in values:
                    raise ConfigurationError("ENV_FILE", "duplicate configuration field")
                values[key] = binding.value
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeError):
        raise ConfigurationError(
            "ENV_FILE", "cannot read installation configuration file"
        ) from None
    return values


def _read_user_environment(excluded: set[str]) -> dict[str, str]:
    """Read HKCU explicitly; never expand registry strings or mutate the registry."""
    values = {}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            count = winreg.QueryInfoKey(key)[1]
            for index in range(count):
                name, value, kind = winreg.EnumValue(key, index)
                name = name.upper()
                if not name.startswith(PREFIX) or name in excluded:
                    continue
                if kind not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) or not isinstance(value, str):
                    raise ConfigurationError("USER_ENVIRONMENT", "requires string values")
                values[name] = value
    except FileNotFoundError:
        return {}
    except OSError:
        raise ConfigurationError(
            "USER_ENVIRONMENT", "cannot read current user environment"
        ) from None
    return values


def _service_values(entries, values, sources, source):
    known = set(INT_DEFAULTS) | STRING_FIELDS | OPTIONAL_INTS
    for key, value in entries.items():
        key = key.upper()
        if not key.startswith(PREFIX):
            continue
        name = key[len(PREFIX) :]
        if name not in known:
            raise ConfigurationError("UNKNOWN_SETTING", "unrecognized service setting")
        if name in values:
            continue
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError(name, "explicit value must not be empty")
        values[name] = value
        sources[name] = source


def _read_configuration_sources(environ: Mapping[str, str] | None = None):
    env = {k.upper(): v for k, v in (os.environ if environ is None else environ).items()}
    local = env.get("LOCALAPPDATA")
    if not local:
        raise ConfigurationError("USER_DIRECTORY", "LOCALAPPDATA is required")
    root = _absolute_local_path(local, "USER_DIRECTORY") / "ZhenzhenSeedanceVideo"
    values, sources = {}, {}
    _service_values(_read_dotenv(installation_root() / ".env"), values, sources, "dotenv")
    _service_values(env, values, sources, "environment")
    user = _read_user_environment({PREFIX + name for name in values})
    _service_values(user, values, sources, "user_environment")
    return root, values, sources


def load_configuration(environ: Mapping[str, str] | None = None) -> Configuration:
    root, values, sources = _read_configuration_sources(environ)
    return _parse_configuration(root, values, sources)


def _parse_configuration(root, values, sources) -> Configuration:
    if "API_KEY" not in values:
        raise ConfigurationError("API_KEY", "required; generic API_KEY is not an alias")
    if any(c.isspace() for c in values["API_KEY"]):
        raise ConfigurationError("API_KEY", "whitespace is not allowed")

    mode = values.get("EXECUTION_MODE", "local")
    if mode not in {"local", "provider"}:
        raise ConfigurationError("EXECUTION_MODE", "requires local or provider")

    limits: dict[str, int | None] = dict(INT_DEFAULTS)
    limits["DOWNLOAD_BYTES_LIMIT"] = None
    for name in set(INT_DEFAULTS) | OPTIONAL_INTS:
        if name not in values:
            continue
        raw = values[name]
        if not raw.isascii() or not raw.isdecimal():
            raise ConfigurationError(name, "requires a decimal integer")
        number = int(raw)
        if number > 2**63 - 1 or (number == 0 and name != "TRACKING_TIMEOUT_SECONDS"):
            raise ConfigurationError(name, "out of range")
        limits[name] = number
    for lower, upper in (
        ("CONNECT_TIMEOUT_SECONDS", "REQUEST_TIMEOUT_SECONDS"),
        ("WAIT_DEFAULT_SECONDS", "WAIT_MAX_SECONDS"),
        ("PAGE_DEFAULT_SIZE", "PAGE_MAX_SIZE"),
        ("DIAGNOSTIC_BYTES_LIMIT", "TOOL_RESPONSE_BYTES_LIMIT"),
        ("TOOL_RESPONSE_BYTES_LIMIT", "RPC_FRAME_BYTES_LIMIT"),
    ):
        if limits[lower] > limits[upper]:
            raise ConfigurationError(lower, f"must not exceed {upper}")
    if limits["HEARTBEAT_SECONDS"] >= limits["LEASE_TIMEOUT_SECONDS"]:
        raise ConfigurationError("LEASE_TIMEOUT_SECONDS", "must exceed heartbeat interval")

    output = _absolute_local_path(values.get("OUTPUT_DIR", str(root / "outputs")), "OUTPUT_DIR")
    proxy = values.get("PROXY_URL")
    if proxy:
        try:
            parsed = urlsplit(proxy)
            _ = parsed.port
            valid = (
                parsed.scheme in {"http", "https"}
                and parsed.hostname
                and parsed.path in {"", "/"}
                and not parsed.query
                and not parsed.fragment
            )
        except ValueError:
            valid = False
        if not valid:
            raise ConfigurationError("PROXY_URL", "requires an HTTP or HTTPS proxy URL")
    ca = _absolute_local_path(values["CA_FILE"], "CA_FILE") if "CA_FILE" in values else None
    if ca is not None and not ca.is_file():
        raise ConfigurationError("CA_FILE", "CA file does not exist")
    return Configuration(
        root=root,
        output_dir=output,
        api_key=values["API_KEY"],
        proxy_url=proxy,
        proxy_bypass=_validate_bypass(values["PROXY_BYPASS"]) if "PROXY_BYPASS" in values else (),
        ca_file=ca,
        limits=MappingProxyType(limits),
        sources=MappingProxyType(sources),
        explicit=frozenset(values),
        execution_mode=mode,
    )


class ConfigurationConflict(ValueError):
    def __init__(self, names: list[str]):
        self.names = tuple(PREFIX + name for name in sorted(names))
        super().__init__("CONFIG_CONFLICT: " + ", ".join(self.names))


def accept_client_configuration(
    backend: Configuration, environ: Mapping[str, str] | None = None
) -> Configuration:
    """Validate explicit client values without changing the running snapshot."""
    root, explicit, sources = _read_configuration_sources(environ)
    return accept_explicit_configuration(backend, root, explicit, sources)


def accept_explicit_configuration(backend, root, explicit, sources=None) -> Configuration:
    """Compare a frontend's resolved values without reading backend config again."""
    checked, checked_sources = {}, {}
    _service_values(
        {PREFIX + name: value for name, value in explicit.items()},
        checked,
        checked_sources,
        "client",
    )
    explicit = checked
    sources = sources or checked_sources
    if root != backend.root:
        raise ConfigurationConflict(["USER_DIRECTORY"])
    effective = {name: str(value) for name, value in backend.limits.items() if value is not None}
    effective.update(
        API_KEY=backend.api_key,
        OUTPUT_DIR=str(backend.output_dir),
        EXECUTION_MODE=backend.execution_mode,
    )
    if backend.proxy_url:
        effective["PROXY_URL"] = backend.proxy_url
    if backend.proxy_bypass:
        effective["PROXY_BYPASS"] = ",".join(backend.proxy_bypass)
    if backend.ca_file:
        effective["CA_FILE"] = str(backend.ca_file)
    effective.update(explicit)
    candidate = _parse_configuration(root, effective, sources)
    fields = {
        "API_KEY": "api_key",
        "OUTPUT_DIR": "output_dir",
        "PROXY_URL": "proxy_url",
        "PROXY_BYPASS": "proxy_bypass",
        "CA_FILE": "ca_file",
        "EXECUTION_MODE": "execution_mode",
    }
    conflicts = []
    for name in explicit:
        left = getattr(backend, fields[name]) if name in fields else backend.limits[name]
        right = getattr(candidate, fields[name]) if name in fields else candidate.limits[name]
        equal = (
            hmac.compare_digest(left.encode(), right.encode())
            if name == "API_KEY"
            else left == right
        )
        if not equal:
            conflicts.append(name)
    if conflicts:
        raise ConfigurationConflict(conflicts)
    return backend
