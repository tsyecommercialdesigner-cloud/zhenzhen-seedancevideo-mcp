"""Conservative release-fact classifier and evidence checks for the CI gate."""

import difflib
import hashlib
import json
import os
import re
import subprocess
import tempfile
import tomllib
from pathlib import Path
from urllib.parse import unquote, urlsplit

from ci_evidence import PASSIVE_FACT_FILES, current_evidence, input_fingerprint
from markdown_it import MarkdownIt

SECRET = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9_-]{24,}|"
    r"[?&](?:X-Tos-Signature|X-Amz-Signature)=",
    re.IGNORECASE,
)


def git(*args):
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8")


def _markdown_release_paragraphs(old, new, path):
    """Only replace README version facts; never modify a fenced command."""
    if path != "README.md":
        return False
    before, after = old.splitlines(), new.splitlines()
    prefix = "当前版本 **"
    changes = difflib.SequenceMatcher(a=before, b=after, autojunk=False).get_opcodes()
    for operation, i, j, k, end in changes:
        if operation == "equal":
            continue
        if operation != "replace" or j - i != 1 or end - k != 1:
            return False
        if not before[i].startswith(prefix) or not after[k].startswith(prefix):
            return False
        if sum(line.lstrip().startswith("```") for line in before[:i]) % 2:
            return False
        marker = "本地生命周期"
        if marker not in before[i] or marker not in after[k]:
            return False
        if before[i].split(marker, 1)[1] != after[k].split(marker, 1)[1]:
            return False
        fact = after[k].split(marker, 1)[0]
        release_url = (
            r"https://github\.com/tsyecommercialdesigner-cloud/"
            r"zhenzhen-seedancevideo-mcp/releases/tag/v[0-9A-Za-z.]+"
        )
        shape = (
            r"当前版本 \*\*[0-9A-Za-z.]+\*\*，已发布为\[开发预发行版\]\("
            + release_url
            + r"\)，标签提交 `[0-9a-f]{40}`。"
        )
        if not re.fullmatch(shape, fact):
            return False
    return True


def _release_records(old, new):
    """Free-form verification prose is not machine-verifiable; run full checks."""
    return False


def _resource_records(old, new):
    """Only append records explicitly owned by release work, not mutate inputs."""
    before, after = json.loads(old), json.loads(new)
    if not isinstance(before, list) or not isinstance(after, list):
        return False
    if len(after) <= len(before) or after[: len(before)] != before:
        return False
    required = {
        "path",
        "purpose",
        "version",
        "task",
        "owner",
        "status",
        "sha256",
        "release_condition",
        "cleanup",
    }
    for row in after[len(before) :]:
        if not isinstance(row, dict) or set(row) != required:
            return False
        if not all(isinstance(row[k], str) for k in required):
            return False
        if (row["purpose"], row["task"], row["status"]) != (
            "published-release-asset",
            "release-fact-backfill",
            "published",
        ):
            return False
        if (row["owner"], row["release_condition"], row["cleanup"]) != (
            "release owner",
            "retain published asset",
            "do not delete published asset",
        ):
            return False
        if not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            return False
    return True


def classify(base, head):
    """Fail closed on unknown paths, malformed files, deletions and non-fact edits."""
    names = git("diff", "--name-only", "--no-renames", f"{base}...{head}").splitlines()
    if not names or not set(names) <= PASSIVE_FACT_FILES:
        return False
    for name in names:
        if name == "MANUAL.md":
            # Explicit project exception: Agent and human review manual changes.
            continue
        old, new = git("show", f"{base}:{name}"), git("show", f"{head}:{name}")
        if SECRET.search(new):
            return False
        if name == "README.md":
            valid = _markdown_release_paragraphs(old, new, name)
        elif name.endswith(".json"):
            valid = _resource_records(old, new)
        else:
            valid = _release_records(old, new)
        if not valid:
            return False
    return True


def local_links(root, names):
    """Parse Markdown and reject missing local links without fetching remote sites."""
    root = Path(root).resolve()
    for name in names:
        if name == "MANUAL.md":
            continue
        file = root / name
        if file.suffix != ".md":
            continue
        tokens = MarkdownIt("commonmark").parse(file.read_text(encoding="utf-8"))
        for token in tokens:
            for child in token.children or []:
                if child.type not in {"link_open", "image"}:
                    continue
                target = child.attrGet("href") or child.attrGet("src") or ""
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                resolved = (file.parent / unquote(parsed.path)).resolve()
                if not resolved.is_relative_to(root) or not resolved.exists():
                    return False
    return True


def gh_json(endpoint):
    raw = subprocess.check_output(
        ["gh", "api", endpoint], text=True, encoding="utf-8", stderr=subprocess.DEVNULL
    )
    return json.loads(raw)


def release_source_reachable(release_commit, target="HEAD", main="refs/remotes/origin/main"):
    """Accept a published main merge when its release-source parent is in the target."""

    def ancestor(left, right):
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", left, right],
            capture_output=True,
            check=False,
        )
        if result.returncode not in (0, 1):
            raise ValueError("Cannot determine release ancestry")
        return result.returncode == 0

    if not ancestor(release_commit, main):
        return False
    if ancestor(release_commit, target):
        return True
    parents = git("rev-list", "--parents", "-n", "1", release_commit).split()
    return len(parents) == 3 and ancestor(parents[2], target)


def verify_release(repository, root, base, head):
    """Use GitHub's release and ref APIs; never trust facts claimed by a PR alone."""
    root = Path(root)
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    if not re.fullmatch(r"[0-9A-Za-z.]+", version):
        return False
    tag = f"v{version}"
    release = gh_json(f"repos/{repository}/releases/tags/{tag}")
    if release.get("draft") or release.get("tag_name") != tag:
        return False
    ref = gh_json(f"repos/{repository}/git/ref/tags/{tag}")["object"]
    if ref["type"] == "tag":
        ref = gh_json(f"repos/{repository}/git/tags/{ref['sha']}")["object"]
    if ref["type"] != "commit" or not re.fullmatch(r"[0-9a-f]{40}", ref["sha"]):
        return False
    if not release_source_reachable(ref["sha"]):
        return False
    expected = {
        f"zhenzhen_seedancevideo_mcp-{version}.tar.gz",
        f"zhenzhen_seedancevideo_mcp-{version}-py3-none-any.whl",
    }
    assets = {item["name"]: item for item in release["assets"]}
    if not expected <= assets.keys() or "SHA256SUMS.txt" not in assets:
        return False
    if any(not assets[name].get("digest") for name in expected | {"SHA256SUMS.txt"}):
        raise ValueError("GitHub did not provide asset digests")
    with tempfile.TemporaryDirectory(prefix="ci-release-facts-") as tmp:
        subprocess.run(
            [
                "gh",
                "release",
                "download",
                tag,
                "--repo",
                repository,
                "--pattern",
                "SHA256SUMS.txt",
                "--dir",
                tmp,
            ],
            check=True,
            capture_output=True,
        )
        manifest = Path(tmp) / "SHA256SUMS.txt"
        checksum_digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
        if assets["SHA256SUMS.txt"].get("digest") != f"sha256:{checksum_digest}":
            return False
        lines = manifest.read_text(encoding="utf-8-sig").splitlines()
        sums = {}
        for line in lines:
            match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?([^/\\]+)", line.strip())
            if not match or match[2] in sums:
                return False
            sums[match[2]] = match[1].lower()
    for name in expected:
        if assets[name].get("digest") != f"sha256:{sums.get(name)}":
            return False
    name = "docs/test-resource-register.json"
    if name in git("diff", "--name-only", f"{base}...{head}").splitlines():
        before = json.loads(git("show", f"{base}:{name}"))
        after = json.loads(git("show", f"{head}:{name}"))
        for row in after[len(before) :]:
            asset = row["path"].rsplit("/", 1)[-1]
            if row["version"] != tag or asset not in expected:
                return False
            if row["path"] != f"https://github.com/{repository}/releases/download/{tag}/{asset}":
                return False
            if row["sha256"] != sums[asset]:
                return False
    readme = (root / "README.md").read_text(encoding="utf-8")
    return tag in readme and ref["sha"] in readme


def evidence_matches(evidence, expected, run, pull, base_is_descendant):
    """Validate metadata; caller obtains run/artifact/PR from the GitHub API."""
    if not base_is_descendant or run.get("conclusion") != "success":
        return False
    if run.get("event") != "pull_request" or run.get("status") != "completed":
        return False
    if not pull.get("merged") or pull.get("head", {}).get("sha") != run.get("head_sha"):
        return False
    if pull.get("head", {}).get("repo", {}).get("full_name") != expected["repository"]:
        return False
    if pull.get("base", {}).get("ref") not in {"dev", "main"}:
        return False
    keys = (
        "schema",
        "scope",
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
    if any(evidence.get(key) != expected.get(key) for key in keys):
        return False
    return (
        str(run.get("id")) == evidence.get("run_id")
        and str(run.get("run_attempt")) == evidence.get("run_attempt")
        and evidence.get("event") == "pull_request"
        and evidence.get("workflow_ref", "").startswith(
            f"{expected['repository']}/.github/workflows/pr-checks.yml@"
        )
        and bool(re.fullmatch(r"[0-9a-f]{40}", evidence.get("source_commit", "")))
        and bool(re.fullmatch(r"[0-9a-f]{40}", evidence.get("source_tree", "")))
    )


def trusted_run(repository, base, expected):
    """Locate a retained successful run for a merged same-repository PR."""
    response = gh_json(
        f"repos/{repository}/actions/workflows/pr-checks.yml/runs?status=success&per_page=100"
    )
    for run in response["workflow_runs"]:
        if run.get("event") != "pull_request" or run.get("run_attempt") != 1:
            continue
        if run.get("path") != ".github/workflows/pr-checks.yml":
            continue
        if run.get("head_repository", {}).get("full_name") != repository:
            continue
        pulls = gh_json(f"repos/{repository}/commits/{run['head_sha']}/pulls")
        pulls = [pull for pull in pulls if pull.get("merged_at") and pull.get("merge_commit_sha")]
        if not pulls:
            continue
        artifacts = gh_json(f"repos/{repository}/actions/runs/{run['id']}/artifacts")
        name = f"windows-candidate-{run['id']}"
        matching = [a for a in artifacts["artifacts"] if a["name"] == name and not a["expired"]]
        if len(matching) != 1:
            continue
        with tempfile.TemporaryDirectory(prefix="ci-trusted-evidence-") as tmp:
            subprocess.run(
                [
                    "gh",
                    "run",
                    "download",
                    str(run["id"]),
                    "--repo",
                    repository,
                    "--name",
                    name,
                    "--dir",
                    tmp,
                ],
                check=True,
                capture_output=True,
            )
            evidence = json.loads((Path(tmp) / "VERIFICATION_EVIDENCE.json").read_text())
        source = gh_json(f"repos/{repository}/git/commits/{evidence['source_commit']}")
        if source.get("tree", {}).get("sha") != evidence.get("source_tree"):
            continue
        if run["head_sha"] not in [parent["sha"] for parent in source.get("parents", [])]:
            continue
        fetch = subprocess.run(
            ["git", "fetch", "--no-tags", "origin", evidence["source_commit"]],
            capture_output=True,
            check=False,
        )
        if (
            fetch.returncode
            or input_fingerprint(evidence["source_commit"]) != expected["operational_inputs_sha256"]
        ):
            continue
        for pull in pulls:
            full = gh_json(f"repos/{repository}/pulls/{pull['number']}")
            ancestry = (
                subprocess.run(
                    ["git", "merge-base", "--is-ancestor", full["merge_commit_sha"], base],
                    check=False,
                    capture_output=True,
                ).returncode
                == 0
            )
            if evidence_matches(evidence, expected, run, full, ancestry):
                return run["id"]
    return None


def main():
    """Report reuse only after all checks; all failures conservatively select full."""
    result = "false"
    reason = "No eligible, verified release backfill"
    try:
        base = os.environ["BASE_SHA"]
        head = os.environ["HEAD_SHA"]
        repository = os.environ["GITHUB_REPOSITORY"]
        if not re.fullmatch(r"[0-9a-f]{40}", base) or not re.fullmatch(r"[0-9a-f]{40}", head):
            raise ValueError("Missing PR commit identity")
        if not (input_fingerprint(base) == input_fingerprint(head) == input_fingerprint("HEAD")):
            raise ValueError("Operational inputs differ across merge")
        names = git("diff", "--name-only", "--no-renames", f"{base}...{head}").splitlines()
        if not classify(base, head) or not local_links(Path.cwd(), names):
            raise ValueError("Change is not a permitted release-fact backfill")
        if subprocess.run(
            ["git", "diff", "--check", f"{base}...{head}", "--", ".", ":(exclude)MANUAL.md"]
        ).returncode:
            raise ValueError("Diff formatting failed")
        if not verify_release(repository, Path.cwd(), base, head):
            print("Release facts conflict with GitHub; verification failed")
            return 1
        run_id = trusted_run(repository, base, current_evidence())
        if not run_id:
            raise ValueError("No matching trusted full-check evidence")
        result = "true"
        reason = f"Release facts checked; full verification reused from trusted run {run_id}"
    except Exception:
        # Do not print API errors, environment values, or PR-supplied content.
        reason = "Evidence unavailable, invalid, or change outside supported fact-only scope"
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"reuse={result}\n")
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as summary:
        summary.write(
            f"### CI scope\n{reason}\n"
            "MANUAL.md content is excluded from CI review; Agent and human review required.\n"
            "No candidate package is reused when this gate skips the build.\n"
        )
    print(reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
