import asyncio
import json
from types import SimpleNamespace

from zhenzhen_seedance_video.diagnostics import Diagnostics, safe_record
from zhenzhen_seedance_video.error_codes import (
    PUBLIC_ERROR_CODES,
    PublicInputError,
    PublicOperationError,
)
from zhenzhen_seedance_video.production import CODE
from zhenzhen_seedance_video.provider import ProviderFailure, classify_http
from zhenzhen_seedance_video.storage import StorageError
from zhenzhen_seedance_video.task_state import StateError
from zhenzhen_seedance_video.tools import Tools


def test_dynamic_public_codes_have_matching_safe_diagnostics():
    facade = Tools.__new__(Tools)
    facade.db = SimpleNamespace(storage_fault=False)
    facade.diagnostics = None
    failures = [
        ProviderFailure(CODE),
        ProviderFailure(),
        classify_http(403, phase="query", api_id="seedance-video"),
        classify_http(503, phase="query", api_id="seedance-video"),
        classify_http(400, phase="query", api_id="seedance-video"),
        StorageError("STORAGE_CONSTRAINT"),
        StorageError("DATABASE_OPEN_FAILED"),
    ]
    for code in (
        "LOCK_BUSY",
        "LOCK_UNAVAILABLE",
        "QUERY_RESPONSE_INVALID",
        "QUERY_REQUEST_TIMEOUT",
    ):
        assert code in PUBLIC_ERROR_CODES
        assert safe_record(code, "query")["code"] == code
    for failure in failures:
        code = getattr(failure, "code", str(failure))
        assert code in PUBLIC_ERROR_CODES
        assert safe_record(code, "query")["code"] == code

        async def get_task(failure=failure, **kwargs):
            raise failure

        result = asyncio.run(facade._handler(get_task)({}))
        assert result["error"] == result["diagnostic"]["code"] == code


def test_provider_unknown_code_is_not_exposed():
    facade = Tools.__new__(Tools)
    facade.db = SimpleNamespace(storage_fault=False)
    facade.diagnostics = None

    async def get_task(**kwargs):
        raise ProviderFailure("SYNTHETIC_PRIVATE_PROVIDER_CODE")

    result = asyncio.run(facade._handler(get_task)({}))
    assert result["error"] == result["diagnostic"]["code"] == "INTERNAL_ERROR"
    assert "SYNTHETIC_PRIVATE" not in json.dumps(result)


def test_unknown_exception_message_and_code_are_not_public():
    facade = Tools.__new__(Tools)
    facade.db = SimpleNamespace(storage_fault=False)
    facade.diagnostics = None

    class ForgedError(Exception):
        code = "SYNTHETIC_PRIVATE_KEY"

    async def get_task(**kwargs):
        raise ForgedError("SYNTHETIC_PRIVATE_PROMPT")

    response = asyncio.run(facade._handler(get_task)({}))
    assert response["error"] == response["diagnostic"]["code"] == "INTERNAL_ERROR"
    assert "SYNTHETIC_PRIVATE" not in json.dumps(response)


def test_trusted_error_identity_and_diagnostic_roundtrip(tmp_path):
    facade = Tools.__new__(Tools)
    facade.db = SimpleNamespace(storage_fault=False)
    facade.diagnostics = Diagnostics(tmp_path / "logs")

    async def get_task(**kwargs):
        raise RuntimeError("TASK_NOT_FOUND")

    result = asyncio.run(facade._handler(get_task)({}))
    assert result["error"] == result["diagnostic"]["code"] == "INTERNAL_ERROR"

    class ForgedError(Exception):
        code = "TASK_NOT_FOUND"

    async def get_task(**kwargs):
        raise ForgedError("private")

    result = asyncio.run(facade._handler(get_task)({}))
    assert result["error"] == result["diagnostic"]["code"] == "INTERNAL_ERROR"

    class ForgedStateError(StateError):
        pass

    async def get_task(**kwargs):
        raise ForgedStateError("TASK_NOT_FOUND", {"secret": "SYNTHETIC_PRIVATE"})

    result = asyncio.run(facade._handler(get_task)({}))
    assert result["error"] == result["diagnostic"]["code"] == "INTERNAL_ERROR"
    assert "SYNTHETIC_PRIVATE" not in json.dumps(result)

    async def get_task(**kwargs):
        raise PublicInputError("INVALID_CURSOR")

    result = asyncio.run(facade._handler(get_task)({}))
    assert result["error"] == result["diagnostic"]["code"] == "INVALID_CURSOR"
    assert facade.diagnostics.get(result["diagnostic"]["diagnostic_id"]) == result["diagnostic"]
    facade.diagnostics.close()


def test_broken_unknown_exception_never_inspects_its_attributes():
    facade = Tools.__new__(Tools)
    facade.db = SimpleNamespace(storage_fault=False)
    facade.diagnostics = None

    class Broken(Exception):
        @property
        def code(self):
            raise RuntimeError("private-code")

        def __str__(self):
            raise RuntimeError("private-string")

    async def get_task(**kwargs):
        raise Broken()

    response = asyncio.run(facade._handler(get_task)({}))
    assert response["error"] == response["diagnostic"]["code"] == "INTERNAL_ERROR"
    assert "private" not in json.dumps(response)

    class BrokenString(Exception):
        code = "TASK_NOT_FOUND"

        def __str__(self):
            raise RuntimeError("private-string")

    async def get_task(**kwargs):
        raise BrokenString()

    response = asyncio.run(facade._handler(get_task)({}))
    assert response["error"] == response["diagnostic"]["code"] == "INTERNAL_ERROR"


def test_trusted_code_property_failure_is_safely_handled(monkeypatch):
    facade = Tools.__new__(Tools)
    facade.db = SimpleNamespace(storage_fault=False)
    facade.diagnostics = None

    def fail(_):
        raise RuntimeError("private-code")

    monkeypatch.setattr(PublicInputError, "code", property(fail), raising=False)

    async def get_task(**kwargs):
        raise PublicInputError("INVALID_CURSOR")

    response = asyncio.run(facade._handler(get_task)({}))
    assert response["error"] == response["diagnostic"]["code"] == "INTERNAL_ERROR"
    assert "private-code" not in json.dumps(response)


def test_cleanup_diagnostic_stage_and_roundtrip(tmp_path):
    facade = Tools.__new__(Tools)
    facade.db = SimpleNamespace(storage_fault=False)
    facade.diagnostics = Diagnostics(tmp_path / "logs")

    async def retry_material_cleanup(**kwargs):
        raise PublicOperationError("MATERIAL_CLEANUP_NOT_AUTHORIZED")

    result = asyncio.run(facade._handler(retry_material_cleanup)({}))
    record = result["diagnostic"]
    assert result["error"] == record["code"] == "MATERIAL_CLEANUP_NOT_AUTHORIZED"
    assert record["stage"] == "cleanup"
    assert facade.diagnostics.get(record["diagnostic_id"]) == record
    facade.diagnostics.close()


def test_operation_diagnostic_stages():
    facade = Tools.__new__(Tools)
    facade.db = SimpleNamespace(storage_fault=False)
    facade.diagnostics = None
    for name, expected in (
        ("submit_video", "admission"),
        ("retry_unsubmitted_task", "submit"),
        ("retry_task_download", "download"),
        ("get_task", "query"),
    ):

        async def operation(**kwargs):
            raise PublicOperationError("INVALID_CURSOR")

        operation.__name__ = name
        result = asyncio.run(facade._handler(operation)({}))
        assert result["diagnostic"]["stage"] == expected


def test_untrusted_details_never_enter_summary_or_logs(tmp_path, capsys):
    store = Diagnostics(tmp_path / "logs", secrets=("secret-key",))
    details = {
        "traceback": "raise Exception(secret-key)" * 10000,
        "html": "<script>read private file</script>",
        "nested": {"Authorization": "Bearer secret-key"},
        "url": "https://example.com/video?X-Tos-Signature=private",
        "remote_status": "failed",
        "attempt": 2,
    }
    result = store.record("REMOTE_TASK_FAILED", "query", task_id="task_local_1", details=details)
    assert store.get(result["diagnostic_id"]) == result
    store.close()
    raw = (tmp_path / "logs/events.jsonl").read_text(encoding="utf-8")
    for text in ("secret-key", "script", "private", "raise", "Signature"):
        assert text not in raw
    assert result["task_id"] == "task_local_1"
    assert result["details"] == {"attempt": 2, "remote_status": "failed"}
    assert result["allowed_actions"] == ["get_task"]
    assert capsys.readouterr().out == ""


def test_redaction_before_limits_and_unknown_error():
    result = safe_record(
        "<html>secret</html>",
        "ignore instructions",
        task_id="secret-task",
        secrets=("secret",),
        summary_limit=5,
    )
    assert result["task_id"] is None
    assert result["code"] == "INTERNAL_ERROR"
    assert result["stage"] == "unknown"
    assert len(result["summary"]) == 5


def test_rotation_and_restart_query_are_bounded(tmp_path):
    store = Diagnostics(tmp_path / "logs", max_bytes=1200, backups=2)
    first = store.record("QUERY_FAILED", "query")
    for _ in range(30):
        last = store.record("QUERY_FAILED", "query")
    store.close()
    paths = list((tmp_path / "logs").iterdir())
    assert len(paths) <= 3
    assert all(path.stat().st_size <= 1200 for path in paths)
    restarted = Diagnostics(tmp_path / "logs", max_bytes=1200, backups=2)
    assert restarted.get(first["diagnostic_id"]) is None
    assert restarted.get(last["diagnostic_id"]) == last
    assert restarted.get("../events.jsonl") is None
    restarted.close()


def test_query_resanitizes_modified_record(tmp_path):
    store = Diagnostics(tmp_path / "logs")
    result = store.record("QUERY_FAILED", "query")
    store.close()
    result["summary"] = "read secret file"
    result["details"] = {"api_key": "secret"}
    (tmp_path / "logs/events.jsonl").write_text(json.dumps(result) + "\n", encoding="utf-8")
    restarted = Diagnostics(tmp_path / "logs")
    assert "secret" not in str(restarted.get(result["diagnostic_id"]))
    restarted.close()


def test_business_diagnostics_ignore_untrusted_values(tmp_path):
    store = Diagnostics(tmp_path / "logs", secrets=("private-key",))
    for code in ("PROMPT_AUTHORIZATION_REQUIRED", "TASK_NOT_FOUND"):
        record = store.record(
            code,
            "query",
            details={
                "field": "private-key",
                "url": "https://example.invalid/?signature=private",
                "prompt": "private-prompt",
                "traceback": "private-key",
            },
        )
        restored = store.get(record["diagnostic_id"])
        assert restored == record and record["code"] == code
        assert not any(
            secret in json.dumps(restored)
            for secret in ("private-key", "private-prompt", "signature")
        )
    store.close()


def test_legacy_unknown_code_falls_back_safely(tmp_path):
    store = Diagnostics(tmp_path / "logs")
    record = store.record("QUERY_FAILED", "query")
    store.close()
    record.update(code="old-private-code", summary="private-path", details={"url": "private"})
    (tmp_path / "logs/events.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
    reopened = Diagnostics(tmp_path / "logs")
    restored = reopened.get(record["diagnostic_id"])
    assert restored["code"] == "INTERNAL_ERROR"
    assert "private" not in json.dumps(restored)
    reopened.close()
