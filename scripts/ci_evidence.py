"""Record CI evidence after full checks; never treat a cache entry as proof."""

import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

PASSIVE_FACT_FILES = frozenset(
    {
        "README.md",
        "MANUAL.md",
        "docs/test-resource-register.json",
        "docs/verification-add-local-video-generation-service.md",
    }
)


def command(*args):
    return subprocess.check_output(args, text=True, encoding="utf-8").strip()


def input_fingerprint(revision):
    listing = subprocess.check_output(["git", "ls-tree", "-r", "-z", revision])
    records = []
    for record in listing.split(b"\0"):
        if not record:
            continue
        meta, name = record.split(b"\t", 1)
        if name.decode("utf-8") not in PASSIVE_FACT_FILES:
            records.append(meta + b"\t" + name + b"\0")
    return hashlib.sha256(b"".join(records)).hexdigest()


def current_evidence():
    revision = command("git", "rev-parse", "HEAD")
    evidence = {
        "schema": 1,
        "scope": "full-windows-lint-format-tests-build",
        "source_commit": revision,
        "source_tree": command("git", "rev-parse", "HEAD^{tree}"),
        "operational_inputs_sha256": input_fingerprint("HEAD"),
        "excluded_passive_fact_files": sorted(PASSIVE_FACT_FILES),
        "workflow_ref": os.environ.get("GITHUB_WORKFLOW_REF", ""),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "repository": os.environ.get("GITHUB_REPOSITORY", ""),
        "event": os.environ.get("GITHUB_EVENT_NAME", ""),
        "python": platform.python_version(),
        "uv": command("uv", "--version"),
        "git": command("git", "--version"),
        "gh": command("gh", "--version").splitlines()[0],
        "runner_os": os.environ.get("RUNNER_OS", ""),
        "runner_arch": os.environ.get("RUNNER_ARCH", ""),
        "image_os": os.environ.get("ImageOS", ""),
        "image_version": os.environ.get("ImageVersion", ""),
    }
    if any(
        not evidence[key]
        for key in (
            "workflow_ref",
            "run_id",
            "repository",
            "runner_os",
            "runner_arch",
            "image_os",
            "image_version",
        )
    ):
        raise RuntimeError("CI provenance is incomplete")
    return evidence


def main():
    evidence = current_evidence()
    Path(sys.argv[1]).write_text(
        json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
