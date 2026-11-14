"""Bounded diagnostic records: untrusted strings never become log messages."""

import json
import logging
import re
import threading
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .windows_security import protect_directory, reject_reparse_path

CATALOG = {
    "REMOTE_TASK_FAILED": ("供应商报告任务失败", False, ("get_task",)),
    "RESPONSE_INVALID": ("供应商响应无法按已确认契约解析", False, ("refresh_task",)),
    "CAPABILITY_UNVERIFIED": ("此接口能力尚未核实", False, ("get_capabilities",)),
    "QUERY_FAILED": ("查询暂未取得有效结果", True, ("get_task", "refresh_task")),
    "DOWNLOAD_FAILED": ("产物尚未完成下载", True, ("retry_task_download",)),
    "STORAGE_FAULT": ("本地持久化异常，自动执行已受保护", False, ("get_service_status",)),
    "INTERNAL_ERROR": ("本地操作异常，请按诊断标识核查", False, ("get_service_status",)),
}
STAGES = frozenset({"startup", "admission", "submit", "query", "download", "cleanup", "storage"})
STATES = frozenset({"queued", "in_progress", "completed", "failed"})


def _identifier(value):
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        return value
    return None


def safe_record(code, stage, *, task_id=None, details=None, secrets=(), summary_limit=512):
    """Allowlist first, secret removal second, length limits last.

    HTML, traceback, provider instructions and arbitrary nested objects are
    deliberately discarded. The caller supplies internal task IDs only.
    """
    code = code if isinstance(code, str) and code in CATALOG else "INTERNAL_ERROR"
    message, retryable, actions = CATALOG[code]
    record = {
        "diagnostic_id": str(uuid.uuid4()),
        "code": code,
        "stage": stage if isinstance(stage, str) and stage in STAGES else "unknown",
        "summary": message,
        "retryable": retryable,
        "needs_attention": True,
        "allowed_actions": list(actions),
        "task_id": _identifier(task_id),
        "details": {},
    }
    if isinstance(details, dict):
        for key in ("attempt", "http_status"):
            value = details.get(key)
            if type(value) is int and 0 <= value <= 2147483647:
                record["details"][key] = value
        state = details.get("remote_status")
        if isinstance(state, str) and state in STATES:
            record["details"]["remote_status"] = state
    # Even allowlisted identifier fields must not leak a configured secret.
    for secret in secrets:
        if secret and record["task_id"] and secret in record["task_id"]:
            record["task_id"] = None
    record["summary"] = record["summary"][:summary_limit]
    return record


class Diagnostics:
    """Single-backend structured log; no root logger or stdout handler.

    Retention applies only to diagnostic files. It never touches task state.
    """

    def __init__(
        self,
        directory: Path,
        *,
        max_bytes=10485760,
        backups=5,
        detail_limit=8192,
        summary_limit=512,
        secrets=(),
    ):
        if min(max_bytes, backups, detail_limit, summary_limit) <= 0:
            raise ValueError("INVALID_DIAGNOSTIC_LIMIT")
        self.directory = directory
        self.detail_limit = detail_limit
        self.summary_limit = summary_limit
        self._secrets = tuple(secrets)
        self._lock = threading.RLock()
        protect_directory(directory)
        self.paths = [directory / "events.jsonl"] + [
            directory / f"events.jsonl.{index}" for index in range(1, backups + 1)
        ]
        for path in self.paths:
            reject_reparse_path(path)
        self.handler = RotatingFileHandler(
            self.paths[0], maxBytes=max_bytes, backupCount=backups, encoding="utf-8"
        )
        self.logger = logging.Logger("private-diagnostics", level=logging.INFO)
        self.logger.propagate = False
        self.logger.addHandler(self.handler)
        self.max_bytes = max_bytes

    def record(self, code, stage, *, task_id=None, details=None):
        record = safe_record(
            code,
            stage,
            task_id=task_id,
            details=details,
            secrets=self._secrets,
            summary_limit=self.summary_limit,
        )
        encoded = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) + 2 > min(self.detail_limit, self.max_bytes):
            raise ValueError("DIAGNOSTIC_LIMIT_TOO_SMALL_FOR_REQUIRED_FIELDS")
        with self._lock:
            self.logger.info(encoded)
            self.handler.flush()
        return record

    def get(self, diagnostic_id):
        try:
            uuid.UUID(diagnostic_id)
        except (ValueError, TypeError, AttributeError):
            return None
        with self._lock:
            for path in self.paths:
                reject_reparse_path(path)
                if not path.exists():
                    continue
                # Bound even externally modified log files; do not return raw data.
                if path.stat().st_size > self.max_bytes:
                    continue
                with path.open("r", encoding="utf-8") as stream:
                    for line in stream:
                        if len(line.encode("utf-8")) > self.detail_limit:
                            continue
                        try:
                            data = json.loads(line)
                        except ValueError:
                            continue
                        if not isinstance(data, dict) or data.get("diagnostic_id") != diagnostic_id:
                            continue
                        result = safe_record(
                            data.get("code"),
                            data.get("stage"),
                            task_id=data.get("task_id"),
                            details=data.get("details"),
                            secrets=self._secrets,
                            summary_limit=self.summary_limit,
                        )
                        result["diagnostic_id"] = diagnostic_id
                        return result
        return None

    def close(self):
        with self._lock:
            self.handler.close()
            self.logger.removeHandler(self.handler)
