import json

from zhenzhen_seedance_video.diagnostics import Diagnostics, safe_record


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
