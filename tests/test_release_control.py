"""Release decisions use synthetic metadata and never contact GitHub."""

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

scripts = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location("release_control", scripts / "release_control.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def test_run_identity_requires_actual_merged_main_candidate():
    sha, head, repo = "a" * 40, "b" * 40, "example/repo"
    run = {
        "status": "completed",
        "conclusion": "success",
        "event": "pull_request",
        "path": ".github/workflows/pr-checks.yml",
        "head_repository": {"full_name": repo},
        "run_attempt": 1,
        "head_sha": head,
    }
    pr = {
        "merged_at": "2026-01-01",
        "merge_commit_sha": sha,
        "base": {"ref": "main"},
        "head": {"sha": head, "repo": {"full_name": repo}},
    }
    release.validate_run(run, [pr], repo, sha)
    with pytest.raises(ValueError):
        release.validate_run(run, [{**pr, "merge_commit_sha": "c" * 40}], repo, sha)
    with pytest.raises(ValueError):
        release.validate_run({**run, "conclusion": "failure"}, [pr], repo, sha)


def test_candidate_looks_up_main_merge_not_dev_head(monkeypatch):
    main_sha, head, repo = "a" * 40, "b" * 40, "example/repo"
    run = {
        "status": "completed",
        "conclusion": "success",
        "event": "pull_request",
        "path": ".github/workflows/pr-checks.yml",
        "head_repository": {"full_name": repo},
        "run_attempt": 1,
        "head_sha": head,
    }
    pr = {
        "merged_at": "2026-01-01",
        "merge_commit_sha": main_sha,
        "base": {"ref": "main"},
        "head": {"sha": head, "repo": {"full_name": repo}},
    }
    seen = []

    def api(endpoint):
        seen.append(endpoint)
        if endpoint.endswith("/actions/runs/123"):
            return run
        if endpoint.endswith(f"/commits/{main_sha}/pulls"):
            return [pr]
        if "/jobs?" in endpoint:
            return {
                "jobs": [
                    {
                        "name": "windows",
                        "conclusion": "success",
                        "steps": [
                            {"name": name, "conclusion": "success"}
                            for name in (
                                "Build packages",
                                "Record candidate identity and checksums",
                                "Check lint and formatting",
                                "Run isolated tests",
                            )
                        ],
                    }
                ]
            }
        if "/artifacts?" in endpoint:
            return {"artifacts": [{"name": "windows-candidate-123", "expired": False}]}
        pytest.fail(f"Unexpected API endpoint: {endpoint}")

    monkeypatch.setattr(release, "api", api)
    assert release.candidate_run(repo, "123", main_sha) == (run, "full", True)
    assert any(f"/commits/{main_sha}/pulls" in endpoint for endpoint in seen)


def test_release_assets_are_exact_and_verified(tmp_path):
    names = [
        "zhenzhen_seedancevideo_mcp-0.1.0.dev1.tar.gz",
        "zhenzhen_seedancevideo_mcp-0.1.0.dev1-py3-none-any.whl",
    ]
    lines = []
    for name in names:
        data = name.encode()
        (tmp_path / name).write_bytes(data)
        lines.append(f"{hashlib.sha256(data).hexdigest()}  {name}")
    manifest = tmp_path / "SHA256SUMS.txt"
    manifest.write_text("\n".join(lines) + "\n", encoding="ascii")
    assert set(release.verify_assets(tmp_path, "0.1.0.dev1")) == set(names)
    (tmp_path / names[0]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="digest"):
        release.verify_assets(tmp_path, "0.1.0.dev1")
    manifest.write_text("\n".join(lines + lines[:1]), encoding="ascii")
    with pytest.raises(ValueError, match="Malformed"):
        release.verify_assets(tmp_path, "0.1.0.dev1")


def test_release_requires_build_and_full_or_reused_tests():
    def job(lint, test, build="success"):
        return [
            {
                "name": "windows",
                "conclusion": "success",
                "steps": [
                    {"name": "Build packages", "conclusion": build},
                    {"name": "Record candidate identity and checksums", "conclusion": "success"},
                    {"name": "Check lint and formatting", "conclusion": lint},
                    {"name": "Run isolated tests", "conclusion": test},
                ],
            }
        ]

    assert release.validate_jobs(job("success", "success")) == "full"
    assert release.validate_jobs(job("skipped", "skipped")) == "reused"
    with pytest.raises(ValueError):
        release.validate_jobs(job("skipped", "success"))
    with pytest.raises(ValueError):
        release.validate_jobs(job("success", "success", "skipped"))


def test_candidate_evidence_binds_tree_run_and_merge_head():
    tree, head, source_sha = "a" * 40, "b" * 40, "c" * 40
    run = {"head_sha": head, "run_attempt": 1}
    source = {"tree": {"sha": tree}, "parents": [{"sha": head}]}
    metadata = {
        "source_commit": source_sha,
        "source_tree": tree,
        "run_id": "123",
        "event": "pull_request",
        "run_attempt": "1",
        "scope": "full-windows-lint-format-tests-build",
    }
    release.validate_source(run, source, tree, metadata, "full", "123")
    for broken in ({**metadata, "source_tree": "d" * 40}, {**metadata, "run_id": "124"}):
        with pytest.raises(ValueError):
            release.validate_source(run, source, tree, broken, "full", "123")
    with pytest.raises(ValueError):
        release.validate_source(run, {**source, "parents": []}, tree, metadata, "full", "123")


def test_reused_evidence_requires_equal_runtime_and_inputs():
    keys = (
        "schema",
        "source_tree",
        "operational_inputs_sha256",
        "excluded_passive_fact_files",
        "repository",
        "python",
        "uv",
        "git",
        "gh",
        "runner_os",
        "runner_arch",
        "image_os",
        "image_version",
    )
    candidate = dict.fromkeys(keys, "same")
    previous = {**candidate, "scope": "full-windows-lint-format-tests-build"}
    release.validate_reused(candidate, previous)
    release.validate_reused(candidate, {**previous, "source_tree": "different-tree"})
    with pytest.raises(ValueError, match="differs"):
        release.validate_reused(candidate, {**previous, "image_version": "changed"})
    with pytest.raises(ValueError, match="differs"):
        release.validate_reused(candidate, {**previous, "scope": "candidate-build-reused-checks"})


@pytest.mark.parametrize(
    ("changed", "previous_fingerprint", "valid"),
    [
        (b"README.md\0", "same", True),
        (b"docs/test-resource-register.json\0", "same", True),
        (b"MANUAL.md\0", "same", False),
        (b"README.md\0src/server.py\0", "same", False),
        (b"README.md\0", "tampered", False),
    ],
)
def test_candidate_fact_backfill_rechecks_git_inputs(
    tmp_path, monkeypatch, changed, previous_fingerprint, valid
):
    repo, head, old_head = "example/repo", "a" * 40, "b" * 40
    candidate_sha, previous_sha, candidate_tree, previous_tree = (
        "c" * 40,
        "d" * 40,
        "e" * 40,
        "f" * 40,
    )
    shared = dict.fromkeys(
        (
            "schema",
            "excluded_passive_fact_files",
            "python",
            "uv",
            "git",
            "gh",
            "runner_os",
            "runner_arch",
            "image_os",
            "image_version",
        ),
        "same",
    )
    shared.update(
        repository=repo,
        operational_inputs_sha256="same",
        event="pull_request",
        run_attempt="1",
        workflow_ref=f"{repo}/.github/workflows/pr-checks.yml@refs/pull/1/merge",
    )
    candidate = {
        **shared,
        "source_commit": candidate_sha,
        "source_tree": candidate_tree,
        "run_id": "2",
        "scope": "candidate-build-reused-checks",
        "reused_run_id": "1",
    }
    previous = {
        **shared,
        "source_commit": previous_sha,
        "source_tree": previous_tree,
        "run_id": "1",
        "scope": "full-windows-lint-format-tests-build",
    }
    (tmp_path / "CANDIDATE_EVIDENCE.json").write_text(
        release.json.dumps(candidate), encoding="utf-8"
    )
    previous_run = {
        "conclusion": "success",
        "event": "pull_request",
        "run_attempt": 1,
        "head_sha": old_head,
        "path": ".github/workflows/pr-checks.yml",
        "head_repository": {"full_name": repo},
    }

    def api(endpoint):
        if endpoint.endswith(candidate_sha):
            return {"tree": {"sha": candidate_tree}, "parents": [{"sha": head}]}
        if endpoint.endswith(previous_sha):
            return {"tree": {"sha": previous_tree}, "parents": [{"sha": old_head}]}
        if endpoint.endswith("/actions/runs/1"):
            return previous_run
        if endpoint.endswith("/artifacts?per_page=100"):
            return {"artifacts": [{"name": "windows-candidate-1", "expired": False}]}
        if endpoint.endswith("/pulls"):
            return [
                {
                    "merged_at": "yes",
                    "merge_commit_sha": "9" * 40,
                    "base": {"ref": "dev"},
                    "head": {"sha": old_head, "repo": {"full_name": repo}},
                }
            ]
        pytest.fail(f"unexpected API endpoint {endpoint}")

    def download(repo, run_id, folder):
        (folder / "VERIFICATION_EVIDENCE.json").write_text(
            release.json.dumps(previous), encoding="utf-8"
        )

    monkeypatch.setattr(release, "api", api)
    monkeypatch.setattr(release, "download_run", download)
    monkeypatch.setattr(
        release.subprocess,
        "run",
        lambda *args, **kwargs: release.subprocess.CompletedProcess(args, 0),
    )
    monkeypatch.setattr(release.subprocess, "check_output", lambda *args, **kwargs: changed)
    monkeypatch.setattr(
        release,
        "input_fingerprint",
        lambda rev: previous_fingerprint if rev == previous_sha else "same",
    )
    monkeypatch.setattr(release, "verify_assets", lambda *args: {"current-package": "digest"})
    run = {"head_sha": head, "run_attempt": 1}
    if valid:
        assert release.verify_candidate(
            repo, "2", run, "reused", tmp_path, candidate_tree, "1"
        ) == {"current-package": "digest"}
    else:
        with pytest.raises(ValueError):
            release.verify_candidate(repo, "2", run, "reused", tmp_path, candidate_tree, "1")


def test_prepare_rebuilds_only_if_artifact_expired(tmp_path, monkeypatch):
    main_sha, tree = "a" * 40, "b" * 40
    folder = tmp_path / "assets"
    calls = []
    monkeypatch.setattr(release, "run", lambda *args: tree if "HEAD^{tree}" in args else main_sha)
    monkeypatch.setattr(release, "api", lambda endpoint: {"object": {"sha": main_sha}})
    monkeypatch.setattr(release, "version_at", lambda root: "0.1.0.dev1")
    monkeypatch.setattr(release, "candidate_run", lambda *args: ({}, "full", False))
    monkeypatch.setattr(release, "rebuild_candidate", lambda *args: calls.append("rebuild"))
    monkeypatch.setattr(release, "verify_assets", lambda *args: {"file": "hash"})
    monkeypatch.setattr(release, "verify_install", lambda *args: calls.append("install"))
    release.prepare("example/repo", main_sha, "123", folder)
    assert calls == ["rebuild", "install"]
    prepared = release.json.loads((folder / "RELEASE_PREPARED.json").read_text())
    assert prepared["scope"] == "rebuilt-full"
    assert prepared["main_sha"] == main_sha


def test_rebuild_runs_full_checks_before_constructing_manifest(tmp_path, monkeypatch):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[:2] == ["uv", "build"]:
            for name in (
                "zhenzhen_seedancevideo_mcp-0.1.0.dev1.tar.gz",
                "zhenzhen_seedancevideo_mcp-0.1.0.dev1-py3-none-any.whl",
            ):
                (tmp_path / name).write_bytes(name.encode())

    monkeypatch.setattr(release.subprocess, "run", fake_run)
    result = release.rebuild_candidate(tmp_path, "0.1.0.dev1")
    assert len(result) == 2
    assert [cmd[3] if cmd[1] == "run" else cmd[1] for cmd in commands] == [
        "ruff",
        "ruff",
        "pytest",
        "build",
    ]


def test_rebuild_failure_stops_before_build(tmp_path, monkeypatch):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[3] == "pytest":
            raise release.subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(release.subprocess, "run", fake_run)
    with pytest.raises(release.subprocess.CalledProcessError):
        release.rebuild_candidate(tmp_path, "0.1.0.dev1")
    assert len(commands) == 3


def test_publish_refuses_changed_main_before_any_mutation(tmp_path, monkeypatch):
    main_sha, tree = "a" * 40, "b" * 40
    (tmp_path / "RELEASE_PREPARED.json").write_text(
        release.json.dumps(
            {
                "repository": "example/repo",
                "main_sha": main_sha,
                "version": "0.1.0.dev1",
                "tree": tree,
                "assets": {"file": "hash"},
            }
        )
    )
    monkeypatch.setattr(release, "version_at", lambda root: "0.1.0.dev1")
    monkeypatch.setattr(release, "run", lambda *args: tree)
    monkeypatch.setattr(release, "verify_assets", lambda *args: {"file": "hash"})
    monkeypatch.setattr(release, "api", lambda endpoint: {"object": {"sha": "c" * 40}})
    monkeypatch.setattr(release.subprocess, "run", lambda *args, **kwargs: pytest.fail("mutation"))
    with pytest.raises(ValueError, match="main changed"):
        release.publish("example/repo", main_sha, tmp_path, tmp_path / "notes", False)


@pytest.mark.parametrize("digest_matches", [True, False])
def test_publish_only_promotes_verified_draft(tmp_path, monkeypatch, digest_matches):
    main_sha, tree = "a" * 40, "b" * 40
    checksums = tmp_path / "SHA256SUMS.txt"
    checksums.write_text("checksum", encoding="ascii")
    hashes = {"package.whl": "c" * 64}
    (tmp_path / "RELEASE_PREPARED.json").write_text(
        release.json.dumps(
            {
                "repository": "example/repo",
                "main_sha": main_sha,
                "version": "0.1.0.dev1",
                "tree": tree,
                "assets": hashes,
            }
        )
    )
    monkeypatch.setattr(release, "version_at", lambda root: "0.1.0.dev1")
    monkeypatch.setattr(release, "run", lambda *args: tree)
    monkeypatch.setattr(release, "verify_assets", lambda *args: hashes)
    monkeypatch.setattr(release, "remote_tag_absent", lambda tag: None)
    asset_digest = "c" * 64 if digest_matches else "d" * 64
    checksum_digest = hashlib.sha256(checksums.read_bytes()).hexdigest()
    calls = []

    def api(endpoint):
        if "/heads/" in endpoint:
            return {"object": {"sha": main_sha}}
        if "/git/ref/tags/" in endpoint:
            return {"object": {"type": "commit", "sha": main_sha}}
        if "?per_page=100" in endpoint and not calls:
            calls.append("existing-check")
            return []
        calls.append(endpoint)
        result = {
            "draft": len(calls) == 2,
            "tag_name": "v0.1.0.dev1",
            "assets": [
                {"name": "package.whl", "digest": f"sha256:{asset_digest}"},
                {"name": "SHA256SUMS.txt", "digest": f"sha256:{checksum_digest}"},
            ],
        }
        return [result] if "?per_page=100" in endpoint else result

    monkeypatch.setattr(release, "api", api)
    commands = []
    monkeypatch.setattr(release.subprocess, "run", lambda args, **kwargs: commands.append(args))
    if digest_matches:
        release.publish("example/repo", main_sha, tmp_path, tmp_path / "notes", False)
        assert [command[1] for command in commands] == ["api", "release", "release"]
        assert [command[2] for command in commands[1:]] == ["create", "edit"]
    else:
        with pytest.raises(ValueError, match="Draft assets"):
            release.publish("example/repo", main_sha, tmp_path, tmp_path / "notes", False)
        assert [command[1] for command in commands] == ["api", "release"]
        assert commands[1][2] == "create"
