"""SDK v2 stdio proxy. All business state belongs to the shared backend."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from .runtime import connect_or_start
from .tools import READ_ONLY


class ReconnectingClient:
    """Reconnect only before a new call; never replay an uncertain operation."""

    def __init__(self, connect, client):
        self.connect = connect
        self.client = client
        self.lock = asyncio.Lock()

    async def call(self, method, params=None, *, wait_seconds=30):
        async with self.lock:
            if self.client.writer.is_closing() or self.client.receiver.done():
                await self.client.close()
                self.client = await self.connect()
            client = self.client
        return await client.call(method, params, wait_seconds=wait_seconds)

    async def close(self):
        async with self.lock:
            await self.client.close()


def create_server(connect=connect_or_start):
    client = None

    @asynccontextmanager
    async def lifespan(server):
        nonlocal client
        client = ReconnectingClient(connect, await connect())
        try:
            yield {}
        finally:
            await client.close()

    server = MCPServer("zhenzhen-seedance-video", lifespan=lifespan)

    def tool(name):
        return server.tool(
            annotations=ToolAnnotations(
                read_only_hint=name in READ_ONLY,
                destructive_hint=name not in READ_ONLY,
                idempotent_hint=name in READ_ONLY,
                open_world_hint=name
                in {
                    "submit_video",
                    "upscale_video",
                    "refresh_task",
                    "resume_task_tracking",
                    "retry_unsubmitted_task",
                    "retry_task_download",
                },
            )
        )

    @tool("get_service_status")
    async def get_service_status() -> dict[str, Any]:
        """本地健康、额度与供应商状态分开报告；不发起健康探测。"""
        return await client.call("get_service_status", {}, wait_seconds=120)

    @tool("get_capabilities")
    async def get_capabilities(
        api_id: str | None = None, model_id: str | None = None
    ) -> dict[str, Any]:
        """按 API 和模型返回已声明能力及待核实项。"""
        return await client.call(
            "get_capabilities", {"api_id": api_id, "model_id": model_id}, wait_seconds=120
        )

    @tool("preflight_video_task")
    async def preflight_video_task(
        request: dict, api_id: str = "seedance-video", allow_once: bool = False
    ) -> dict[str, Any]:
        """无上传、无接收副作用的参数与授权预检；不保证随后接收成功。"""
        return await client.call(
            "preflight_video_task",
            {"request": request, "api_id": api_id, "allow_once": allow_once},
            wait_seconds=120,
        )

    @tool("submit_video")
    async def submit_video(
        request_key: str, request: dict, allow_once: bool = False
    ) -> dict[str, Any]:
        """正式接收即授权自动执行；allow_once 仅用于本次用户已同意优化。"""
        return await client.call(
            "submit_video",
            {"request_key": request_key, "request": request, "allow_once": allow_once},
            wait_seconds=120,
        )

    @tool("upscale_video")
    async def upscale_video(request_key: str, request: dict) -> dict[str, Any]:
        """独立超分任务，不自动串联生成任务。"""
        return await client.call(
            "upscale_video", {"request_key": request_key, "request": request}, wait_seconds=120
        )

    @tool("find_task_by_request_key")
    async def find_task_by_request_key(request_key: str) -> dict[str, Any]:
        """响应丢失后按原请求标识只读找回，不重新生成。"""
        return await client.call(
            "find_task_by_request_key", {"request_key": request_key}, wait_seconds=120
        )

    @tool("get_task")
    async def get_task(task_id: str) -> dict[str, Any]:
        """读取一致本地状态与有效参数摘要，不访问上游。"""
        return await client.call("get_task", {"task_id": task_id}, wait_seconds=120)

    @tool("list_tasks")
    async def list_tasks(
        cursor: str | None = None,
        limit: int | None = None,
        remote_state: str | None = None,
        attention_reason: str | None = None,
        needs_attention: bool = False,
    ) -> dict[str, Any]:
        """稳定游标分页；异常非消费式；不承诺跨页快照。"""
        return await client.call(
            "list_tasks",
            {
                "cursor": cursor,
                "limit": limit,
                "remote_state": remote_state,
                "attention_reason": attention_reason,
                "needs_attention": needs_attention,
            },
            wait_seconds=120,
        )

    @tool("wait_task")
    async def wait_task(
        task_id: str, after_version: int, timeout_seconds: float | None = None
    ) -> dict[str, Any]:
        """按已知版本有界等待；超时或取消等待不取消任务。"""
        return await client.call(
            "wait_task",
            {
                "task_id": task_id,
                "after_version": after_version,
                "timeout_seconds": timeout_seconds,
            },
            wait_seconds=120,
        )

    @tool("refresh_task")
    async def refresh_task(task_id: str) -> dict[str, Any]:
        """显式单次远端刷新，可能保存新事实并授权下载，不是只读操作。"""
        return await client.call("refresh_task", {"task_id": task_id}, wait_seconds=120)

    @tool("resume_task_tracking")
    async def resume_task_tracking(task_id: str, expected_version: int) -> dict[str, Any]:
        """以新预算恢复自动跟踪，保留历史。"""
        return await client.call(
            "resume_task_tracking",
            {"task_id": task_id, "expected_version": expected_version},
            wait_seconds=120,
        )

    @tool("retry_unsubmitted_task")
    async def retry_unsubmitted_task(task_id: str, expected_version: int) -> dict[str, Any]:
        """仅通过适配器可靠未创建证据重试，不能用用户声明替代。"""
        return await client.call(
            "retry_unsubmitted_task",
            {"task_id": task_id, "expected_version": expected_version},
            wait_seconds=120,
        )

    @tool("cancel_task")
    async def cancel_task(task_id: str, expected_version: int) -> dict[str, Any]:
        """取消尚未提交的任务；提交后取消能力待核实。"""
        return await client.call(
            "cancel_task",
            {"task_id": task_id, "expected_version": expected_version},
            wait_seconds=120,
        )

    @tool("abandon_task")
    async def abandon_task(
        task_id: str,
        expected_version: int,
        reason: str,
        acknowledge_remote_may_continue: bool = False,
    ) -> dict[str, Any]:
        """放弃本地跟踪并清理托管输入；远端仍可能继续并计费。"""
        return await client.call(
            "abandon_task",
            {
                "task_id": task_id,
                "expected_version": expected_version,
                "reason": reason,
                "acknowledge_remote_may_continue": acknowledge_remote_may_continue,
            },
            wait_seconds=120,
        )

    @tool("repair_task_materials")
    async def repair_task_materials(
        task_id: str, material_id: str, source: str, expected_version: int
    ) -> dict[str, Any]:
        """仅补回未提交任务内容一致的本地托管素材。"""
        return await client.call(
            "repair_task_materials",
            {
                "task_id": task_id,
                "material_id": material_id,
                "source": source,
                "expected_version": expected_version,
            },
            wait_seconds=120,
        )

    @tool("retry_material_cleanup")
    async def retry_material_cleanup(task_id: str, expected_version: int) -> dict[str, Any]:
        """以新预算重试登记的清理待办，不接收任意删除路径。"""
        return await client.call(
            "retry_material_cleanup",
            {"task_id": task_id, "expected_version": expected_version},
            wait_seconds=120,
        )

    @tool("retry_task_download")
    async def retry_task_download(
        task_id: str, expected_version: int, overwrite: bool = False
    ) -> dict[str, Any]:
        """恢复下载；已有异常文件仅在显式 overwrite 时覆盖。"""
        return await client.call(
            "retry_task_download",
            {"task_id": task_id, "expected_version": expected_version, "overwrite": overwrite},
            wait_seconds=120,
        )

    @tool("list_artifacts")
    async def list_artifacts(task_id: str, after: str = "", limit: int = 20) -> dict[str, Any]:
        """分页返回产物绝对路径与摘要，不传输视频或签名 URL。"""
        return await client.call(
            "list_artifacts", {"task_id": task_id, "after": after, "limit": limit}, wait_seconds=120
        )

    @tool("verify_artifact")
    async def verify_artifact(artifact_id: str) -> dict[str, Any]:
        """显式核验并保存外部删改状态，不自动覆盖或下载。"""
        return await client.call("verify_artifact", {"artifact_id": artifact_id}, wait_seconds=120)

    @tool("copy_artifact")
    async def copy_artifact(
        artifact_id: str,
        target_path: str,
        workspace_root: str | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """保留原产物复制；相对路径须提供工作区绝对路径且不能越界。"""
        return await client.call(
            "copy_artifact",
            {
                "artifact_id": artifact_id,
                "target_path": target_path,
                "workspace_root": workspace_root,
                "overwrite": overwrite,
            },
            wait_seconds=120,
        )

    @tool("get_prompt_optimization_policy")
    async def get_prompt_optimization_policy() -> dict[str, Any]:
        """读取同一 Windows 用户共享优化授权。"""
        return await client.call("get_prompt_optimization_policy", {}, wait_seconds=120)

    @tool("set_prompt_optimization_policy")
    async def set_prompt_optimization_policy(
        enabled: bool, expected_version: int, confirmed: bool = False
    ) -> dict[str, Any]:
        """显式授权或撤销总是允许，单次 false 优先。"""
        return await client.call(
            "set_prompt_optimization_policy",
            {"enabled": enabled, "expected_version": expected_version, "confirmed": confirmed},
            wait_seconds=120,
        )

    @tool("get_diagnostic")
    async def get_diagnostic(diagnostic_id: str) -> dict[str, Any]:
        """只返回有界脱敏诊断，不提供原始日志。"""
        return await client.call(
            "get_diagnostic", {"diagnostic_id": diagnostic_id}, wait_seconds=120
        )

    return server


async def run_frontend():
    await create_server().run_stdio_async()
