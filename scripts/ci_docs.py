"""Conservatively classify and check ordinary documentation-only dev PRs."""

import os
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

from ci_backfill import SECRET
from markdown_it import MarkdownIt


def git(*args):
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8")


def eligible(base, merge):
    """Only changed, existing Markdown in reviewed documentation directories."""
    lines = git("diff", "--name-status", "--no-renames", base, merge).splitlines()
    paths = []
    for line in lines:
        status, name = line.split("\t", 1)
        allowed = name in {"README.md", "MANUAL.md", "AGENTS.md"} or name.startswith(
            ("docs/", "openspec/")
        )
        if status != "M" or not allowed or not name.endswith(".md"):
            return []
        paths.append(name)
    return paths


def check_document(root, name):
    root = Path(root).resolve()
    file = (root / name).resolve()
    if not file.is_relative_to(root):
        raise ValueError("Document outside repository")
    source = file.read_text(encoding="utf-8")
    tokens = MarkdownIt("commonmark").parse(source)
    lines = source.splitlines()
    for token in tokens:
        if token.type == "fence":
            end = token.map[1]
            if end <= token.map[0] + 1 or not re.match(
                rf"^\s{{0,3}}{re.escape(token.markup[0])}{{{len(token.markup)},}}\s*$",
                lines[end - 1],
            ):
                raise ValueError("Unclosed Markdown fence")
        for child in token.children or []:
            if child.type not in {"link_open", "image"}:
                continue
            target = child.attrGet("href") or child.attrGet("src") or ""
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            resolved = (file.parent / unquote(parsed.path)).resolve()
            if not resolved.is_relative_to(root) or not resolved.exists():
                raise ValueError("Invalid local link")


def main():
    base = os.environ.get("BASE_SHA", "")
    if os.environ.get("BASE_REF") != "dev" or not re.fullmatch(r"[0-9a-f]{40}", base):
        paths = []
    else:
        paths = eligible(base, "HEAD")
    output = Path(os.environ["GITHUB_OUTPUT"])
    if not paths:
        with output.open("a", encoding="utf-8") as stream:
            stream.write("docs=false\n")
        return 0
    subprocess.run(["git", "diff", "--check", base, "HEAD"], check=True)
    diff = git("diff", "--no-color", base, "HEAD")
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++") and SECRET.search(line):
            raise ValueError("Secret pattern detected")
    for name in paths:
        check_document(Path.cwd(), name)
    with output.open("a", encoding="utf-8") as stream:
        stream.write("docs=true\n")
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as stream:
        stream.write(
            "### CI scope\nDocumentation-only dev PR: Markdown, local links, diff and secret "
            "patterns checked; tests and build not run. Review semantic accuracy separately.\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
