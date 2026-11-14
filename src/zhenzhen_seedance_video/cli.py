"""Executable boundary; never emit operational diagnostics on MCP stdout."""

import argparse
import asyncio
import re
import sys

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="zhenzhen-seedance-video")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("mode", nargs="?", choices=("stdio", "backend"), default="stdio")
    args = parser.parse_args(argv)
    if sys.platform != "win32":
        print("UNSUPPORTED_PLATFORM: Windows is required.", file=sys.stderr)
        return 2
    from .config import ConfigurationError
    from .frontend import run_frontend
    from .network import NetworkError
    from .ownership import OwnershipError
    from .runtime import RuntimeErrorCode, run_backend

    try:
        asyncio.run(run_backend() if args.mode == "backend" else run_frontend())
    except Exception as error:
        pending = [error]
        for _ in range(16):
            if not pending:
                break
            item = pending.pop()
            if isinstance(item, ConfigurationError):
                print(str(item), file=sys.stderr)
                return 2
            if isinstance(item, (RuntimeErrorCode, OwnershipError, NetworkError)) and re.fullmatch(
                r"[A-Z_]{1,64}", str(item)
            ):
                print(str(item), file=sys.stderr)
                return 2
            if isinstance(item, BaseExceptionGroup):
                pending.extend(item.exceptions[:16])
        print(
            "SERVICE_START_OR_RUNTIME_FAILED: inspect local configuration and diagnostics.",
            file=sys.stderr,
        )
        return 2
    return 0
