"""Backend tool facade; provider-dependent methods require an installed adapter."""

import json
import os
import re
from datetime import UTC, datetime

from .admission import authorize, local_inputs
from .diagnostics import safe_record
from .models import get_model
from .preflight import capabilities, preflight
from .queries import Queries
from .storage import StorageError
from .task_state import StateError, TaskState

READ_ONLY = {
    "get_service_status",
    "get_capabilities",
    "preflight_video_task",
    "get_task",
    "find_task_by_request_key",
    "list_tasks",
    "wait_task",
    "get_prompt_optimization_policy",
    "get_diagnostic",
}


class Tools:
    def __init__(
        self, admission, artifacts, cleanup, *, scheduler=None, leases=None, diagnostics=None
    ):
        self.admission, self.artifacts, self.cleanup = admission, artifacts, cleanup
        self.scheduler, self.leases, self.diagnostics = scheduler, leases, diagnostics
        self.db, self.config = admission.db, admission.config
        self.queries = Queries(self.db, self.config)
        self.state = TaskState(self.db)

    async def get_service_status(self) -> dict:
        """本地健康、额度与供应商状态分开报告；不发起健康探测。"""

        def read(c):
            held = c.execute("SELECT coalesce(sum(generation_slot_held),0) FROM tasks").fetchone()[
                0
            ]
            count = c.execute("SELECT count(*) FROM tasks WHERE attention!='[]'").fetchone()[0]
            jobs = {
                r[0]: r[1]
                for r in c.execute("SELECT state,count(*) FROM cleanup_jobs GROUP BY state")
            }
            limit = self.config.limits["GENERATION_CONCURRENCY"]
            return {
                "pid": os.getpid(),
                "phase": "running"
                if not self.leases or self.leases.network_allowed
                else "draining",
                "host_count": len(self.leases.hosts) if self.leases else 0,
                "dispatch_allowed": bool(
                    self.scheduler and (not self.leases or self.leases.dispatch_allowed)
                ),
                "generation_slots_held": held,
                "generation_slots_limit": limit,
                "generation_slots_available": max(0, limit - held),
                "provider": "unverified",
                "execution_mode": self.admission.config.execution_mode,
                "generation_execution": "adapter_installed"
                if self.scheduler
                else "not_implemented",
                "storage_fault": self.db.storage_fault,
                "stale": self.db.storage_fault,
                "attention_count": count,
                "attention_tool": "list_tasks",
                "cleanup": jobs,
            }

        return await self.db.execute(read, write=False)

    async def get_capabilities(
        self, api_id: str | None = None, model_id: str | None = None
    ) -> dict:
        """按 API 和模型返回已声明能力及待核实项。"""
        return capabilities(api_id=api_id, model_id=model_id)

    async def preflight_video_task(
        self, request: dict, api_id: str = "seedance-video", allow_once: bool = False
    ) -> dict:
        """无上传、无接收副作用的参数与授权预检；不保证随后接收成功。"""
        normalized, inputs = local_inputs(request)
        model = get_model(normalized.get("model"), api_id=api_id)
        policy = await self.admission.get_preference()
        authorization = authorize(normalized, policy, allow_once, model.kind)
        if model.kind not in ("upscale", "draft-to-video"):
            normalized["enhance_prompt"] = authorization["enabled"]
        result = preflight(
            normalized,
            configuration=self.config,
            api_id=api_id,
            draft_fact=await self.admission.draft_fact(normalized),
        )
        payload = result.pop("effective_parameters")
        result.update(
            authorization=authorization,
            authorization_checked=True,
            effective_summary={
                "model": payload["model"],
                "seconds": payload.get("seconds"),
                "metadata": {
                    k: v
                    for k, v in payload.get("metadata", {}).items()
                    if k not in ("content", "video_url", "audio_urls")
                },
            },
            local_material_count=len(inputs),
            materials_checked=False,
        )
        return result

    async def submit_video(self, request_key: str, request: dict, allow_once: bool = False) -> dict:
        """正式接收即授权自动执行；allow_once 仅用于本次用户已同意优化。"""
        return await self.admission.submit(request_key, request, allow_once=allow_once)

    async def upscale_video(self, request_key: str, request: dict) -> dict:
        """独立超分任务，不自动串联生成任务。"""
        return await self.admission.submit(request_key, request, api_id="zhenzhen-upscaler")

    async def find_task_by_request_key(self, request_key: str) -> dict:
        """响应丢失后按原请求标识只读找回，不重新生成。"""
        return await self.admission.find(request_key) | {"stale": self.db.storage_fault}

    async def get_task(self, task_id: str) -> dict:
        """读取一致本地状态与有效参数摘要，不访问上游。"""
        return await self.queries.get(task_id)

    async def list_tasks(
        self,
        cursor: str | None = None,
        limit: int | None = None,
        remote_state: str | None = None,
        attention_reason: str | None = None,
        needs_attention: bool = False,
    ) -> dict:
        """稳定游标分页；异常非消费式；不承诺跨页快照。"""
        return await self.queries.list(
            cursor=cursor,
            limit=limit,
            remote_state=remote_state,
            attention_reason=attention_reason,
            needs_attention=needs_attention,
        )

    async def wait_task(
        self, task_id: str, after_version: int, timeout_seconds: float | None = None
    ) -> dict:
        """按已知版本有界等待；超时或取消等待不取消任务。"""
        return await self.queries.wait(task_id, after_version, timeout_seconds)

    def _scheduler(self):
        if self.scheduler is None:
            raise StateError("CAPABILITY_UNVERIFIED")
        return self.scheduler

    async def refresh_task(self, task_id: str) -> dict:
        """显式单次远端刷新，可能保存新事实并授权下载，不是只读操作。"""
        return await self._scheduler().refresh(task_id)

    async def resume_task_tracking(self, task_id: str, expected_version: int) -> dict:
        """以新预算恢复自动跟踪，保留历史。"""
        return await self._scheduler().resume(task_id, expected_version=expected_version)

    async def retry_unsubmitted_task(self, task_id: str, expected_version: int) -> dict:
        """仅通过适配器可靠未创建证据重试，不能用用户声明替代。"""
        return await self._scheduler().retry_not_created(task_id, expected_version=expected_version)

    async def cancel_task(self, task_id: str, expected_version: int) -> dict:
        """取消尚未提交的任务；提交后取消能力待核实。"""
        return await self.state.cancel_unsubmitted(
            task_id, expected_version=expected_version, now=datetime.now(UTC).isoformat()
        )

    async def abandon_task(
        self,
        task_id: str,
        expected_version: int,
        reason: str,
        acknowledge_remote_may_continue: bool = False,
    ) -> dict:
        """放弃本地跟踪并清理托管输入；远端仍可能继续并计费。"""
        return await self.state.abandon(
            task_id,
            expected_version=expected_version,
            reason=reason,
            confirmed=acknowledge_remote_may_continue,
            now=datetime.now(UTC).isoformat(),
        )

    async def repair_task_materials(
        self, task_id: str, material_id: str, source: str, expected_version: int
    ) -> dict:
        """仅补回未提交任务内容一致的本地托管素材。"""
        return await self.admission.repair(
            task_id, material_id, source, expected_version=expected_version
        )

    async def retry_material_cleanup(self, task_id: str, expected_version: int) -> dict:
        """以新预算重试登记的清理待办，不接收任意删除路径。"""
        return await self.cleanup.retry(task_id, expected_version=expected_version)

    async def retry_task_download(
        self, task_id: str, expected_version: int, overwrite: bool = False
    ) -> dict:
        """恢复下载；已有异常文件仅在显式 overwrite 时覆盖。"""
        return await self.artifacts.retry(
            task_id, expected_version=expected_version, overwrite=overwrite
        )

    async def list_artifacts(self, task_id: str, after: str = "", limit: int = 20) -> dict:
        """分页返回产物绝对路径与摘要，不传输视频或签名 URL。"""
        if type(limit) is not int or not 1 <= limit <= self.config.limits["PAGE_MAX_SIZE"]:
            raise ValueError("INVALID_PAGE_SIZE")
        result = await self.artifacts.list(task_id, after=after, limit=min(limit, 100))
        while (
            len(json.dumps(result, ensure_ascii=False).encode())
            > self.config.limits["TOOL_RESPONSE_BYTES_LIMIT"]
            and len(result["items"]) > 1
        ):
            result["items"].pop()
            result["next_cursor"] = result["items"][-1]["artifact_id"]
            result["truncated"] = True
        return result

    async def verify_artifact(self, artifact_id: str) -> dict:
        """显式核验并保存外部删改状态，不自动覆盖或下载。"""
        return await self.artifacts.verify(artifact_id)

    async def copy_artifact(
        self,
        artifact_id: str,
        target_path: str,
        workspace_root: str | None = None,
        overwrite: bool = False,
    ) -> dict:
        """保留原产物复制；相对路径须提供工作区绝对路径且不能越界。"""
        return await self.artifacts.copy(
            artifact_id, target_path, workspace_root=workspace_root, overwrite=overwrite
        )

    async def get_prompt_optimization_policy(self) -> dict:
        """读取同一 Windows 用户共享优化授权。"""
        return await self.admission.get_preference()

    async def set_prompt_optimization_policy(
        self, enabled: bool, expected_version: int, confirmed: bool = False
    ) -> dict:
        """显式授权或撤销总是允许，单次 false 优先。"""
        return await self.admission.set_preference(
            enabled=enabled, expected_version=expected_version, confirmed=confirmed
        )

    async def get_diagnostic(self, diagnostic_id: str) -> dict:
        """只返回有界脱敏诊断，不提供原始日志。"""
        result = self.diagnostics.get(diagnostic_id) if self.diagnostics else None
        return result or {"ok": False, "error": "DIAGNOSTIC_NOT_FOUND"}

    def handlers(self):
        return {name: self._handler(getattr(self, name)) for name in TOOL_NAMES}

    def _handler(self, function):
        async def call(params):
            try:
                if self.db.storage_fault and function.__name__ not in READ_ONLY:
                    raise StorageError("STORAGE_FAULT")
                result = await function(**params)
                if (
                    len(json.dumps(result, ensure_ascii=False).encode())
                    > self.config.limits["TOOL_RESPONSE_BYTES_LIMIT"]
                ):
                    result = {
                        k: v
                        for k, v in result.items()
                        if k
                        in {
                            "task_id",
                            "remote_id",
                            "version",
                            "stage",
                            "remote_state",
                            "delivery",
                            "allowed_actions",
                            "accepted",
                            "request_key",
                        }
                    } | {"truncated": True, "error": "RESPONSE_TOO_LARGE"}
                return result
            except Exception as error:
                code = getattr(error, "code", str(error))
                if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,100}", code):
                    code = (
                        "INVALID_TOOL_INPUT"
                        if isinstance(error, (TypeError, ValueError))
                        else "INTERNAL_ERROR"
                    )
                record = (
                    self.diagnostics.record(code, "query", task_id=params.get("task_id"))
                    if self.diagnostics
                    else safe_record(code, "query", task_id=params.get("task_id"))
                )
                result = {"ok": False, "error": code, "diagnostic": record}
                if isinstance(error, StateError) and error.snapshot:
                    result["task"] = error.snapshot
                return result

        return call


TOOL_NAMES = tuple(
    name
    for name, value in vars(Tools).items()
    if not name.startswith("_") and name != "handlers" and callable(value)
)
