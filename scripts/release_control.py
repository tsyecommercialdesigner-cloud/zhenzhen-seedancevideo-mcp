"""Validate a manually requested release before any GitHub mutation."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import tomllib
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{40}\Z")


class ExpiredEvidence(Exception):
    """An explicitly missing or expired trusted artifact can be rebuilt."""


def run(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True, encoding="utf-8").strip()


def api(endpoint):
    return json.loads(run("gh", "api", endpoint))


def validate_run(run_data, pulls, repo, main_sha):
    """Require a successful same-repository PR run that merged into the requested main."""
    if not SHA.fullmatch(main_sha):
        raise ValueError("Expected a full main SHA")
    if (
        run_data.get("status") != "completed"
        or run_data.get("conclusion") != "success"
        or run_data.get("event") != "pull_request"
        or run_data.get("path", "").split("@", 1)[0] != ".github/workflows/pr-checks.yml"
        or run_data.get("head_repository", {}).get("full_name") != repo
        or not isinstance(run_data.get("run_attempt"), int)
        or run_data["run_attempt"] < 1
        or not SHA.fullmatch(run_data.get("head_sha", ""))
    ):
        raise ValueError("Candidate run is not a trusted successful PR run")
    matches = [
        p
        for p in pulls
        if p.get("merged_at")
        and p.get("merge_commit_sha") == main_sha
        and p.get("base", {}).get("ref") == "main"
        and p.get("head", {}).get("sha") == run_data.get("head_sha")
        and p.get("head", {}).get("repo", {}).get("full_name") == repo
    ]
    if len(matches) != 1:
        raise ValueError("Candidate PR does not identify the current main merge")


def validate_jobs(jobs):
    """A green lightweight run is not a release candidate."""
    selected = [j for j in jobs if j.get("name") == "windows"]
    if len(selected) != 1 or selected[0].get("conclusion") != "success":
        raise ValueError("Missing successful Windows job")
    steps = {s["name"]: s.get("conclusion") for s in selected[0].get("steps", [])}
    if (
        steps.get("Build packages") != "success"
        or steps.get("Record candidate identity and checksums") != "success"
    ):
        raise ValueError("Run did not build a release candidate")
    full = all(
        steps.get(name) == "success" for name in ("Check lint and formatting", "Run isolated tests")
    )
    reused = all(
        steps.get(name) == "skipped" for name in ("Check lint and formatting", "Run isolated tests")
    )
    if not (full or reused):
        raise ValueError("Candidate check scope is incomplete")
    return "full" if full else "reused"


def verify_assets(folder, version):
    """Reject missing, extra, mismatched or path-bearing checksum entries."""
    folder = Path(folder)
    expected = {
        f"zhenzhen_seedancevideo_mcp-{version}.tar.gz",
        f"zhenzhen_seedancevideo_mcp-{version}-py3-none-any.whl",
    }
    entries = {}
    for line in (folder / "SHA256SUMS.txt").read_text(encoding="utf-8-sig").splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?([^/\\]+)", line.strip())
        if not match or match[2] in entries:
            raise ValueError("Malformed checksum manifest")
        entries[match[2]] = match[1].lower()
    if set(entries) != expected:
        raise ValueError("Unexpected release asset set")
    for name, expected_hash in entries.items():
        file = folder / name
        if (
            file.is_symlink()
            or not file.is_file()
            or hashlib.sha256(file.read_bytes()).hexdigest() != expected_hash
        ):
            raise ValueError("Candidate asset digest mismatch")
    return entries


def version_at(root):
    with (Path(root) / "pyproject.toml").open("rb") as file:
        version = tomllib.load(file)["project"]["version"]
    if not re.fullmatch(r"[0-9A-Za-z.]+", version):
        raise ValueError("Invalid project version")
    return version


def validate_source(run_data, source, main_tree, metadata, scope, run_id):
    """Bind an artifact to the candidate run, its synthetic merge and final tree."""
    source_sha = metadata.get("source_commit", "")
    if (
        not SHA.fullmatch(source_sha)
        or metadata.get("source_tree") != main_tree
        or source.get("tree", {}).get("sha") != main_tree
        or run_data.get("head_sha") not in [p.get("sha") for p in source.get("parents", [])]
        or metadata.get("run_id") != str(run_id)
        or metadata.get("event") != "pull_request"
        or metadata.get("run_attempt") != str(run_data.get("run_attempt"))
        or metadata.get("scope")
        != (
            "full-windows-lint-format-tests-build"
            if scope == "full"
            else "candidate-build-reused-checks"
        )
    ):
        raise ValueError("Candidate source evidence does not match the merged tree")


def validate_reused(candidate, previous):
    """Require the same full check inputs and runtime as the earlier evidence."""
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
    if previous.get("scope") != "full-windows-lint-format-tests-build" or any(
        candidate.get(key) != previous.get(key) or not candidate.get(key) for key in keys
    ):
        raise ValueError("Reused evidence differs from candidate inputs or environment")


def available_artifact(artifacts, run_id):
    matches = [a for a in artifacts if a.get("name") == f"windows-candidate-{run_id}"]
    if len(matches) > 1:
        raise ValueError("Ambiguous candidate artifact")
    return bool(matches and not matches[0].get("expired"))


def candidate_run(repo, run_id, main_sha):
    if not run_id.isdecimal():
        raise ValueError("Invalid candidate run ID")
    data = api(f"repos/{repo}/actions/runs/{run_id}")
    if not SHA.fullmatch(data.get("head_sha", "")):
        raise ValueError("Invalid candidate head SHA")
    pulls = api(f"repos/{repo}/commits/{data['head_sha']}/pulls")
    validate_run(data, pulls, repo, main_sha)
    attempt = data["run_attempt"]
    jobs = api(f"repos/{repo}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100")
    scope = validate_jobs(jobs["jobs"])
    artifacts = api(f"repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100")
    return data, scope, available_artifact(artifacts["artifacts"], run_id)


def download_run(repo, run_id, folder):
    subprocess.run(
        [
            "gh",
            "run",
            "download",
            run_id,
            "--repo",
            repo,
            "--name",
            f"windows-candidate-{run_id}",
            "--dir",
            str(folder),
        ],
        check=True,
    )


def verify_candidate(repo, run_id, run_data, scope, folder, tree, version):
    name = "VERIFICATION_EVIDENCE.json" if scope == "full" else "CANDIDATE_EVIDENCE.json"
    evidence = json.loads((folder / name).read_text(encoding="utf-8-sig"))
    if not SHA.fullmatch(evidence.get("source_commit", "")):
        raise ValueError("Invalid source commit")
    source = api(f"repos/{repo}/git/commits/{evidence['source_commit']}")
    validate_source(run_data, source, tree, evidence, scope, run_id)
    if evidence.get("repository") != repo:
        raise ValueError("Candidate belongs to another repository")
    if not evidence.get("workflow_ref", "").startswith(f"{repo}/.github/workflows/pr-checks.yml@"):
        raise ValueError("Candidate workflow identity mismatch")
    if scope == "reused":
        reused_id = evidence.get("reused_run_id", "")
        if not reused_id.isdecimal() or reused_id == run_id:
            raise ValueError("Missing reused run ID")
        previous_run = api(f"repos/{repo}/actions/runs/{reused_id}")
        if (
            previous_run.get("conclusion") != "success"
            or previous_run.get("event") != "pull_request"
            or previous_run.get("path", "").split("@", 1)[0] != ".github/workflows/pr-checks.yml"
            or previous_run.get("head_repository", {}).get("full_name") != repo
            or previous_run.get("run_attempt") != 1
            or not SHA.fullmatch(previous_run.get("head_sha", ""))
        ):
            raise ValueError("Reused run is not trusted")
        previous_artifacts = api(f"repos/{repo}/actions/runs/{reused_id}/artifacts?per_page=100")
        if not available_artifact(previous_artifacts["artifacts"], reused_id):
            raise ExpiredEvidence("Reused evidence expired")
        with tempfile.TemporaryDirectory(prefix="previous-evidence-") as tmp:
            download_run(repo, reused_id, Path(tmp))
            previous = json.loads(
                Path(tmp, "VERIFICATION_EVIDENCE.json").read_text(encoding="utf-8-sig")
            )
        validate_reused(evidence, previous)
        if previous.get("run_id") != reused_id:
            raise ValueError("Reused run identity mismatch")
        previous_sha = previous.get("source_commit", "")
        if not SHA.fullmatch(previous_sha):
            raise ValueError("Invalid reused source commit")
        previous_source = api(f"repos/{repo}/git/commits/{previous_sha}")
        validate_source(previous_run, previous_source, tree, previous, "full", reused_id)
        pulls = api(f"repos/{repo}/commits/{previous_run['head_sha']}/pulls")
        ancestry = [
            p
            for p in pulls
            if p.get("merged_at")
            and p.get("base", {}).get("ref") in {"dev", "main"}
            and p.get("head", {}).get("sha") == previous_run.get("head_sha")
            and p.get("head", {}).get("repo", {}).get("full_name") == repo
            and SHA.fullmatch(p.get("merge_commit_sha") or "")
        ]
        if not any(
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", p["merge_commit_sha"], "HEAD"],
                check=False,
                capture_output=True,
            ).returncode
            == 0
            for p in ancestry
        ):
            raise ValueError("Reused PR is not in main history")
    return verify_assets(folder, version)


def rebuild_candidate(folder, version):
    """Re-run full checks when stored candidate evidence has expired."""
    for command in (
        ["uv", "run", "--frozen", "ruff", "check", "."],
        ["uv", "run", "--frozen", "ruff", "format", "--check", "."],
        ["uv", "run", "--frozen", "pytest", "-q"],
        ["uv", "build", "--offline", "--out-dir", str(folder)],
    ):
        subprocess.run(command, check=True)
    names = [
        f"zhenzhen_seedancevideo_mcp-{version}.tar.gz",
        f"zhenzhen_seedancevideo_mcp-{version}-py3-none-any.whl",
    ]
    lines = [
        f"{hashlib.sha256((folder / name).read_bytes()).hexdigest()}  {name}" for name in names
    ]
    (folder / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
    return verify_assets(folder, version)


def verify_install(folder, version):
    """Install each built distribution in a separate temporary environment."""
    for name in (
        f"zhenzhen_seedancevideo_mcp-{version}.tar.gz",
        f"zhenzhen_seedancevideo_mcp-{version}-py3-none-any.whl",
    ):
        with tempfile.TemporaryDirectory(prefix="release-install-") as tmp:
            environment = Path(tmp) / "venv"
            subprocess.run(["uv", "venv", "--python", "3.12.14", str(environment)], check=True)
            python = environment / "Scripts" / "python.exe"
            requirements = Path(tmp) / "requirements.txt"
            subprocess.run(
                [
                    "uv",
                    "export",
                    "--frozen",
                    "--no-dev",
                    "--no-emit-project",
                    "--format",
                    "requirements-txt",
                    "--output-file",
                    str(requirements),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            subprocess.run(
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    str(python),
                    "-r",
                    str(requirements),
                ],
                check=True,
            )
            subprocess.run(
                [
                    "uv",
                    "pip",
                    "install",
                    "--no-deps",
                    "--python",
                    str(python),
                    str(folder / name),
                ],
                check=True,
            )
            output = run(str(environment / "Scripts" / "zhenzhen-seedance-video.exe"), "--version")
            if output != version:
                raise ValueError("Installed package version mismatch")
            env = {
                key: value
                for key, value in os.environ.items()
                if not key.upper().startswith("ZHENZHEN_SEEDANCE_")
            }
            env.update(
                ZHENZHEN_SEEDANCE_API_KEY="release-probe-placeholder",
                ZHENZHEN_SEEDANCE_EXECUTION_MODE="local",
            )
            subprocess.run(
                [str(python), "-m", "zhenzhen_seedance_video.protocol_probe"],
                cwd=tmp,
                env=env,
                check=True,
                timeout=180,
            )


def prepare(repo, main_sha, run_id, folder):
    if run("git", "rev-parse", "HEAD") != main_sha:
        raise ValueError("Checkout differs from requested main commit")
    if api(f"repos/{repo}/git/ref/heads/main")["object"]["sha"] != main_sha:
        raise ValueError("Remote main changed")
    tree = run("git", "rev-parse", "HEAD^{tree}")
    version = version_at(Path.cwd())
    run_data, scope, present = candidate_run(repo, run_id, main_sha)
    folder.mkdir(parents=True, exist_ok=False)
    rebuilt = not present
    if present:
        download_run(repo, run_id, folder)
        try:
            verify_candidate(repo, run_id, run_data, scope, folder, tree, version)
        except ExpiredEvidence:
            rebuilt = True
            for child in folder.iterdir():
                if not child.is_file() or child.is_symlink():
                    raise ValueError("Unexpected candidate artifact content") from None
                child.unlink()
    if rebuilt:
        rebuild_candidate(folder, version)
    hashes = verify_assets(folder, version)
    verify_install(folder, version)
    manifest = {
        "repository": repo,
        "main_sha": main_sha,
        "tree": tree,
        "version": version,
        "candidate_run": run_id,
        "scope": "rebuilt-full" if rebuilt else scope,
        "assets": hashes,
    }
    (folder / "RELEASE_PREPARED.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print("Release prepared; no tag or release has been created.")


def remote_tag_absent(tag):
    result = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--tags", "origin", f"refs/tags/{tag}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        raise ValueError("Release tag already exists; refusing to replace it")
    if result.returncode != 2:
        raise ValueError("Unable to check remote tag")


def publish(repo, main_sha, folder, notes, prerelease):
    manifest = json.loads((folder / "RELEASE_PREPARED.json").read_text(encoding="utf-8"))
    version = version_at(Path.cwd())
    if manifest.get("repository") != repo or manifest.get("main_sha") != main_sha:
        raise ValueError("Prepared release identity mismatch")
    if manifest.get("version") != version or run("git", "rev-parse", "HEAD^{tree}") != manifest.get(
        "tree"
    ):
        raise ValueError("Prepared release tree or version mismatch")
    hashes = verify_assets(folder, version)
    if hashes != manifest.get("assets"):
        raise ValueError("Prepared release asset identity mismatch")
    if api(f"repos/{repo}/git/ref/heads/main")["object"]["sha"] != main_sha:
        raise ValueError("Remote main changed after preparation")
    tag = f"v{version}"
    remote_tag_absent(tag)
    existing = api(f"repos/{repo}/releases?per_page=100")
    if any(item.get("tag_name") == tag for item in existing):
        raise ValueError("A release or draft already exists; refusing to modify it")
    subprocess.run(
        [
            "gh",
            "api",
            "--method",
            "POST",
            f"repos/{repo}/git/refs",
            "-f",
            f"ref=refs/tags/{tag}",
            "-f",
            f"sha={main_sha}",
        ],
        check=True,
    )
    ref = api(f"repos/{repo}/git/ref/tags/{tag}")["object"]
    if ref.get("type") != "commit" or ref.get("sha") != main_sha:
        raise ValueError("Created tag mismatch; tag retained for inspection")
    files = [str(folder / name) for name in sorted(hashes)] + [str(folder / "SHA256SUMS.txt")]
    command = [
        "gh",
        "release",
        "create",
        tag,
        *files,
        "--repo",
        repo,
        "--target",
        main_sha,
        "--verify-tag",
        "--draft",
        "--title",
        tag,
        "--notes-file",
        str(notes),
    ]
    if prerelease:
        command.append("--prerelease")
    subprocess.run(command, check=True)
    ref = api(f"repos/{repo}/git/ref/tags/{tag}")["object"]
    if ref["type"] == "tag":
        ref = api(f"repos/{repo}/git/tags/{ref['sha']}")["object"]
    if ref.get("type") != "commit" or ref.get("sha") != main_sha:
        raise ValueError("Draft tag mismatch; draft retained for inspection")
    drafts = [
        r
        for r in api(f"repos/{repo}/releases?per_page=100")
        if r.get("draft") and r.get("tag_name") == tag
    ]
    if len(drafts) != 1:
        raise ValueError("Draft not uniquely found; inspect tag and release")
    draft = drafts[0]
    digest = hashlib.sha256((folder / "SHA256SUMS.txt").read_bytes()).hexdigest()
    expected = {**hashes, "SHA256SUMS.txt": digest}
    actual = {item["name"]: item.get("digest") for item in draft.get("assets", [])}
    if not draft.get("draft") or actual != {
        name: f"sha256:{value}" for name, value in expected.items()
    }:
        raise ValueError("Draft assets did not verify; draft retained for inspection")
    subprocess.run(["gh", "release", "edit", tag, "--repo", repo, "--draft=false"], check=True)
    published = api(f"repos/{repo}/releases/tags/{tag}")
    published_assets = {item["name"]: item.get("digest") for item in published.get("assets", [])}
    if published.get("draft") or published_assets != actual:
        raise ValueError("Release status or assets could not be verified after publication")
    print(f"Published {tag} at {main_sha}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "publish"])
    parser.add_argument("--repository", required=True)
    parser.add_argument("--main-sha", required=True)
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--notes", type=Path)
    parser.add_argument("--prerelease", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        raise ValueError("Invalid repository")
    if not SHA.fullmatch(args.main_sha):
        raise ValueError("Invalid main SHA")
    if args.action == "prepare":
        if not args.run_id:
            parser.error("prepare requires --run-id")
        prepare(args.repository, args.main_sha, args.run_id, args.folder)
    else:
        if args.notes is None or not args.notes.is_file():
            parser.error("publish requires an existing --notes file")
        publish(args.repository, args.main_sha, args.folder, args.notes, args.prerelease)


if __name__ == "__main__":
    main()
