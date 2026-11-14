"""Local-only, isolated stdio protocol smoke check for installed distributions."""

import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .config import load_configuration
from .ownership import OwnershipError, ProcessIdentity, confirm_exited


async def _probe(root: Path):
    os.environ["LOCALAPPDATA"] = str(root)
    config = load_configuration()
    if config.execution_mode != "local":
        raise RuntimeError("PROBE_REQUIRES_LOCAL_MODE")
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "zhenzhen_seedance_video", "stdio"],
        env=dict(os.environ),
    )
    discovery = config.root / "runtime" / "discovery.json"
    identity = None
    try:
        with open(os.devnull, "w", encoding="utf-8") as error_sink:  # noqa: ASYNC230
            async with stdio_client(params, errlog=error_sink) as streams:
                async with ClientSession(*streams, read_timeout_seconds=30) as session:
                    init = await session.initialize()
                    names = {item.name for item in (await session.list_tools()).tools}
                    resources = await session.list_resources()
                    templates = await session.list_resource_templates()
                    prompts = await session.list_prompts()
                    if resources.resources or templates.resource_templates or prompts.prompts:
                        raise RuntimeError("PROBE_UNEXPECTED_CAPABILITIES")
                    if not {"get_service_status", "get_capabilities"} <= names:
                        raise RuntimeError("PROBE_TOOLS_MISSING")
                    status = await session.call_tool("get_service_status", {})
                    caps = await session.call_tool("get_capabilities", {})
                    if status.is_error or caps.is_error:
                        raise RuntimeError("PROBE_TOOL_FAILED")
                    if status.structured_content.get("execution_mode") != "local":
                        raise RuntimeError("PROBE_MODE_MISMATCH")
                    if status.structured_content.get("dispatch_allowed") is not False:
                        raise RuntimeError("PROBE_DISPATCH_ENABLED")
                    apis = {
                        item["api_id"]: item["model_count"]
                        for item in caps.structured_content["apis"]
                    }
                    if apis != {"seedance-video": 26, "zhenzhen-upscaler": 1}:
                        raise RuntimeError("PROBE_CAPABILITIES_MISMATCH")
                    data = json.loads(discovery.read_text(encoding="utf-8"))
                    identity = ProcessIdentity(data["pid"], data["created_at"])
                    result = (
                        f"protocol={init.protocol_version} tools={len(names)} "
                        "resources=0 templates=0 prompts=0 local=ok"
                    )
    finally:
        if identity is None and discovery.exists():
            data = json.loads(discovery.read_text(encoding="utf-8"))
            identity = ProcessIdentity(data["pid"], data["created_at"])
        if identity is not None:
            deadline = asyncio.get_running_loop().time() + 45
            while True:
                try:
                    confirm_exited(identity)
                    break
                except OwnershipError as error:
                    if str(error) != "OLD_PROCESS_STILL_ALIVE":
                        raise
                    if asyncio.get_running_loop().time() >= deadline:
                        raise RuntimeError("PROBE_BACKEND_EXIT_UNCONFIRMED") from None
                    await asyncio.sleep(0.2)
    return result


def main():
    if sys.platform != "win32":
        print("PROBE_WINDOWS_REQUIRED", file=sys.stderr)
        return 2
    root = Path(tempfile.mkdtemp(prefix="seedance-probe-"))
    try:
        result = asyncio.run(asyncio.wait_for(_probe(root), timeout=120))
        shutil.rmtree(root)
        print(result)
        return 0
    except Exception as error:
        # Never output configuration values, upstream content, or raw tracebacks.
        print(
            f"PROBE_FAILED: {type(error).__name__}; isolated directory retained: {root}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
