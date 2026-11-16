"""Reuse an independently verified full run only for an identical candidate tree."""

import os
from pathlib import Path

from ci_backfill import git, trusted_run
from ci_evidence import current_evidence


def main():
    run_id = None
    try:
        expected = current_evidence()
        run_id = trusted_run(
            os.environ["GITHUB_REPOSITORY"],
            "HEAD",
            expected,
            exact_tree=git("rev-parse", "HEAD^{tree}").strip(),
        )
    except Exception:
        # A missing, expired or unverifiable run never grants reuse.
        pass
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"reuse={'true' if run_id else 'false'}\n")
        if run_id:
            output.write(f"reuse_run={run_id}\n")
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as summary:
        if run_id:
            summary.write(f"### CI scope\nFull checks reused from trusted run {run_id}; ")
            summary.write("candidate packages are built in this run.\n")
        else:
            summary.write("### CI scope\nNo matching trusted full run; full checks required.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
