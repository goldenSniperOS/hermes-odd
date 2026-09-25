#!/usr/bin/env python3
"""Report upstream drift against ``upstream/upstream.lock.json``.

For each upstream in the lock (gentle-ai, gentle-shell) this script:

1. clones it into a cache directory (``git clone --filter=blob:none``) or
   fetches it when the clone already exists; it never checks files out;
2. finds the default branch (``git ls-remote --symref origin HEAD``) and its
   head commit;
3. checks that the pinned commit exists and is an ancestor of the head
   (otherwise the upstream history was rewritten: error);
4. re-hashes every indexed source at the pin and compares it with the lock
   (a mismatch means the lock itself is wrong: error);
5. classifies every indexed source at the head as ``changed``, ``deleted``
   or ``unchanged``, with the commits that touched it since the pin;
6. lists new upstream files (``git diff --name-status pin..head``) that
   match the watch globs below and are not SDD, as candidates to triage;
7. flags a Go re-render of the canonical ODD routing when ``routing.go`` or
   ``manifest.go`` changed.

Exit codes: 0 clean, 1 drift, 2 error (``--exit-zero`` turns 1 into 0;
errors still exit 2). Output: ``--format json`` (schema
``hermes-odd.upstream-drift/v1``) or ``--format markdown`` (the headings of
the "Upstream port request" issue template, so it doubles as the body of the
scheduled drift issue). Standard library only.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hermes_odd import upstream as upstream_lock  # noqa: E402

REPORT_SCHEMA = "hermes-odd.upstream-drift/v1"
CACHE_ENV = "HERMES_ODD_UPSTREAM_CACHE"
# Default cache: the directory the maintainers already use for read-only
# upstream checkouts. Built from parts: the old project name must not appear
# literally in this repository (tests/test_naming_and_attribution.py).
DEFAULT_CACHE = Path.home() / ".cache" / ("gentle" + "-hermes") / "upstream"

EXIT_CLEAN, EXIT_DRIFT, EXIT_ERROR = 0, 1, 2
# Keeps the markdown report (the issue body) well under GitHub's size limit;
# the JSON report always lists every commit.
MAX_COMMITS_PER_ROW = 8

ISSUE_TITLE = "[upstream-drift] Upstream changes to triage"
# Field labels of .github/ISSUE_TEMPLATE/upstream_port_request.yml, in order;
# a test keeps them in sync with the template.
ISSUE_HEADINGS = (
    "Upstream project",
    "Upstream release or commit",
    "Feature",
    "Portable to Hermes?",
    "Hermes mapping or reason it is not portable",
)

# New upstream files worth triaging, per upstream. ``*`` stays inside one
# path segment, ``**`` crosses segments.
WATCH_GLOBS: Mapping[str, tuple[str, ...]] = {
    "gentle-ai": (
        "internal/assets/skills/*/SKILL.md",
        "internal/assets/skills/*/references/*.md",
        "internal/assets/skills/_shared/odd-*.md",
        "internal/assets/hermes/**",
        "internal/assets/engram/**",
        "internal/assets/generic/**",
        "internal/agents/hermes/**",
        "internal/agents/capabilitymanifest/*.go",
        "internal/components/agentguidance/*.go",
        "internal/components/communitytool/*.go",
        "internal/components/reviewassets/*.go",
        "internal/cli/review*.go",
        "contracts/review-integration/**",
        "contracts/review-provider-contract/**",
    ),
    "gentle-shell": (
        "skills/*/SKILL.md",
        "skills/*/references/*.md",
        "assets/*.md",
        "assets/agents/*.md",
        "assets/chains/*.md",
        "extensions/*.ts",
        "lib/agents-*.ts",
        "lib/odd-*.ts",
        "lib/review-*.ts",
        "lib/session-*.ts",
        "lib/shell-changes*.ts",
        "lib/shell-todo*.ts",
        "contracts/review-provider-contract-mirror/*.json",
        "docs/*.md",
    ),
}
# hermes-odd ships no SDD: such files are never candidates.
SDD_DENY_RE = re.compile(r"sdd|openspec", re.IGNORECASE)
# Upstream tests are development tooling, never shipped behavior.
TEST_DENY_RE = re.compile(r"(_test\.go|\.test\.ts)$|(^|/)(testdata|fixtures|tests)/")
# A change here needs RenderRouting(model.AgentHermes) re-rendered into
# upstream/odd-routing-hermes.canonical.md.
RERENDER_SOURCES = {
    ("gentle-ai", "internal/components/agentguidance/routing.go"),
    ("gentle-ai", "internal/agents/capabilitymanifest/manifest.go"),
}


class DriftError(RuntimeError):
    """A failure that makes the report untrustworthy (exit code 2)."""


@dataclass
class Source:
    upstream: str
    path: str
    sha256: str
    components: list[str] = field(default_factory=list)


def index_sources(lock: Mapping[str, Any]) -> tuple[dict[tuple[str, str], Source], list[str]]:
    """Deduplicate the lock's ``sources`` across components.

    Returns ``({(upstream, path): Source}, errors)``; a source listed with two
    different hashes is an error.
    """
    index: dict[tuple[str, str], Source] = {}
    errors: list[str] = []
    for component, entry in sorted(lock.get("components", {}).items()):
        for raw in entry.get("sources", []):
            key = (raw["upstream"], raw["path"])
            source = index.get(key)
            if source is None:
                source = index[key] = Source(raw["upstream"], raw["path"], raw["sha256"])
            elif source.sha256 != raw["sha256"]:
                errors.append(
                    f"lock lists {key[0]}:{key[1]} with two hashes "
                    f"({source.sha256[:12]} and {raw['sha256'][:12]})"
                )
            if component not in source.components:
                source.components.append(component)
    return index, errors


def resolve_cache(cli_value: str | None, environ: Mapping[str, str] | None = None) -> Path:
    """``--cache`` wins, then ``HERMES_ODD_UPSTREAM_CACHE``, then the default."""
    env = os.environ if environ is None else environ
    if cli_value:
        return Path(cli_value).expanduser()
    if env.get(CACHE_ENV):
        return Path(env[CACHE_ENV]).expanduser()
    return DEFAULT_CACHE


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def is_candidate(
    upstream: str, path: str, globs: Mapping[str, Sequence[str]] = WATCH_GLOBS
) -> bool:
    if SDD_DENY_RE.search(path) or TEST_DENY_RE.search(path):
        return False
    return any(glob_to_regex(g).match(path) for g in globs.get(upstream, ()))


# --- git -----------------------------------------------------------------


def git(repo: Path | None, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    cmd = ["git"]
    if repo is not None:
        cmd += ["-C", str(repo)]
    cmd += list(args)
    result = subprocess.run(cmd, capture_output=True, check=False)
    if check and result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip().splitlines()
        raise DriftError(f"git {' '.join(args[:3])} failed: {detail[-1] if detail else 'error'}")
    return result


def git_text(repo: Path, *args: str) -> str:
    return git(repo, *args).stdout.decode("utf-8", "replace").strip()


def ensure_checkout(checkout: Path, repo_url: str, offline: bool) -> None:
    """Clone (blobless, no checkout) when missing, otherwise fetch."""
    if (checkout / ".git").exists() or (checkout / "HEAD").is_file():
        if not offline:
            git(checkout, "fetch", "--quiet", "--tags", "origin")
        return
    if offline:
        raise DriftError(f"no checkout at {checkout} and --offline was given")
    checkout.parent.mkdir(parents=True, exist_ok=True)
    git(None, "clone", "--quiet", "--filter=blob:none", "--no-checkout", repo_url, str(checkout))


def default_branch(checkout: Path, offline: bool) -> str:
    if not offline:
        out = git_text(checkout, "ls-remote", "--symref", "origin", "HEAD")
        for line in out.splitlines():
            match = re.match(r"^ref:\s+refs/heads/(\S+)\s+HEAD$", line)
            if match:
                return match.group(1)
    ref = git(checkout, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False)
    if ref.returncode == 0:
        return ref.stdout.decode().strip().split("/", 1)[-1]
    raise DriftError("could not detect the default branch of origin")


def head_commit(checkout: Path, branch: str, offline: bool) -> str:
    if not offline:
        git(
            checkout,
            "fetch",
            "--quiet",
            "origin",
            f"+refs/heads/{branch}:refs/remotes/origin/{branch}",
        )
    return git_text(checkout, "rev-parse", f"refs/remotes/origin/{branch}^{{commit}}")


def blob_sha256(checkout: Path, commit: str, path: str) -> str | None:
    result = git(checkout, "show", f"{commit}:{path}", check=False)
    if result.returncode != 0:
        return None
    return hashlib.sha256(result.stdout).hexdigest()


def commit_log(checkout: Path, rev_range: str, *paths: str) -> list[dict[str, str]]:
    args = ["log", "--format=%H%x1f%cs%x1f%s", rev_range]
    if paths:
        args += ["--", *paths]
    out = git_text(checkout, *args)
    commits = []
    for line in out.splitlines():
        sha, date, subject = (line.split("\x1f") + ["", ""])[:3]
        commits.append({"sha": sha, "date": date, "subject": subject})
    return commits


# --- report --------------------------------------------------------------


def check_upstream(
    name: str,
    entry: Mapping[str, Any],
    sources: Sequence[Source],
    cache: Path,
    offline: bool = False,
) -> dict[str, Any]:
    pin = entry["pinned_commit"]
    report: dict[str, Any] = {
        "repo": entry.get("repo", ""),
        "pinned_commit": pin,
        "default_branch": None,
        "head_commit": None,
        "commits_beyond_pin": [],
        "files": [],
        "candidates": [],
        "needs_go_rerender": False,
        "rerender_reasons": [],
        "errors": [],
    }
    checkout = cache / name
    try:
        ensure_checkout(checkout, entry["repo"], offline)
        branch = default_branch(checkout, offline)
        head = head_commit(checkout, branch, offline)
        report["default_branch"], report["head_commit"] = branch, head
        if git(checkout, "cat-file", "-e", f"{pin}^{{commit}}", check=False).returncode != 0:
            raise DriftError(f"pinned commit {pin} does not exist upstream")
        ancestor = git(checkout, "merge-base", "--is-ancestor", pin, head, check=False)
        if ancestor.returncode != 0:
            raise DriftError(
                f"pinned commit {pin[:12]} is not an ancestor of {branch} ({head[:12]}): "
                "upstream history was rewritten"
            )
    except DriftError as exc:
        report["errors"].append(str(exc))
        return report

    report["commits_beyond_pin"] = commit_log(checkout, f"{pin}..{head}")
    for source in sorted(sources, key=lambda s: s.path):
        row: dict[str, Any] = {
            "path": source.path,
            "components": sorted(source.components),
            "lock_sha256": source.sha256,
            "status": "unchanged",
            "head_sha256": None,
            "commits": [],
        }
        at_pin = blob_sha256(checkout, pin, source.path)
        if at_pin is None:
            report["errors"].append(f"{source.path} does not exist at the pin {pin[:12]}")
            row["status"] = "error"
        elif at_pin != source.sha256:
            report["errors"].append(
                f"{source.path}: lock sha256 {source.sha256[:12]} != {at_pin[:12]} at the pin"
            )
            row["status"] = "error"
        else:
            at_head = blob_sha256(checkout, head, source.path)
            row["head_sha256"] = at_head
            if at_head is None:
                row["status"] = "deleted"
            elif at_head != source.sha256:
                row["status"] = "changed"
            if row["status"] != "unchanged":
                row["commits"] = commit_log(checkout, f"{pin}..{head}", source.path)
                if (name, source.path) in RERENDER_SOURCES:
                    report["needs_go_rerender"] = True
                    report["rerender_reasons"].append(f"{source.path} {row['status']}")
        report["files"].append(row)

    indexed = {s.path for s in sources}
    diff = git_text(checkout, "diff", "--no-renames", "--name-status", f"{pin}..{head}")
    for line in diff.splitlines():
        status, _, path = line.partition("\t")
        if status == "A" and path not in indexed and is_candidate(name, path):
            report["candidates"].append({"status": "added", "path": path})
    return report


def build_report(
    lock: Mapping[str, Any], cache: Path, offline: bool = False, now: str | None = None
) -> dict[str, Any]:
    index, errors = index_sources(lock)
    upstreams: dict[str, Any] = {}
    for name, entry in sorted(lock["upstreams"].items()):
        sources = [s for (up, _), s in index.items() if up == name]
        upstreams[name] = check_upstream(name, entry, sources, cache, offline)
    all_errors = list(errors)
    for name, rep in upstreams.items():
        all_errors.extend(f"{name}: {e}" for e in rep["errors"])
    counts = {"changed": 0, "deleted": 0, "unchanged": 0, "candidates": 0, "commits": 0}
    for rep in upstreams.values():
        for row in rep["files"]:
            if row["status"] in counts:
                counts[row["status"]] += 1
        counts["candidates"] += len(rep["candidates"])
        counts["commits"] += len(rep["commits_beyond_pin"])
    drift = counts["changed"] or counts["deleted"] or counts["candidates"]
    status = "error" if all_errors else ("drift" if drift else "clean")
    return {
        "schema": REPORT_SCHEMA,
        "generated_at": now or _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lock_updated": lock.get("updated"),
        "status": status,
        "summary": counts,
        "errors": all_errors,
        "upstreams": upstreams,
    }


def exit_code(report: Mapping[str, Any], exit_zero: bool = False) -> int:
    if report["status"] == "error":
        return EXIT_ERROR
    if report["status"] == "drift" and not exit_zero:
        return EXIT_DRIFT
    return EXIT_CLEAN


def _short(sha: str | None) -> str:
    return (sha or "?")[:12]


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def render_markdown(report: Mapping[str, Any]) -> str:
    ups = report["upstreams"]
    drifting = [
        n
        for n, r in ups.items()
        if r["errors"] or r["candidates"] or any(f["status"] != "unchanged" for f in r["files"])
    ]
    lines = [
        f"Upstream drift report (`{report['schema']}`), generated {report['generated_at']} "
        f"against `upstream/upstream.lock.json` (updated {report['lock_updated']}). "
        f"Status: **{report['status']}**.",
        "",
        f"### {ISSUE_HEADINGS[0]}",
        "",
        ", ".join(drifting) if drifting else "none",
        "",
        f"### {ISSUE_HEADINGS[1]}",
        "",
    ]
    for name, rep in ups.items():
        lines.append(
            f"- {name}: pinned `{_short(rep['pinned_commit'])}` -> "
            f"`{rep['default_branch'] or '?'}` head `{_short(rep['head_commit'])}` "
            f"({len(rep['commits_beyond_pin'])} commits beyond the pin)"
        )
    lines += ["", f"### {ISSUE_HEADINGS[2]}", ""]
    if report["errors"]:
        lines += ["Errors (the report is incomplete):", ""]
        lines += [f"- {_cell(e)}" for e in report["errors"]]
        lines.append("")
    for name, rep in ups.items():
        moved = [f for f in rep["files"] if f["status"] in ("changed", "deleted")]
        lines.append(f"#### {name}")
        lines.append("")
        if moved:
            lines += ["| Source | Status | Components | Commits since pin |", "|---|---|---|---|"]
            for row in moved:
                shown = row["commits"][:MAX_COMMITS_PER_ROW]
                commits = ", ".join(f"`{c['sha'][:8]}` {_cell(c['subject'])}" for c in shown)
                if len(row["commits"]) > len(shown):
                    commits += f", and {len(row['commits']) - len(shown)} more"
                lines.append(
                    f"| `{row['path']}` | {row['status']} | {', '.join(row['components'])} "
                    f"| {commits or '-'} |"
                )
        else:
            lines.append("No indexed source changed.")
        lines.append("")
        if rep["candidates"]:
            lines.append("New upstream files to triage:")
            lines.append("")
            lines += [f"- `{c['path']}`" for c in rep["candidates"]]
            lines.append("")
        unchanged = sum(1 for f in rep["files"] if f["status"] == "unchanged")
        lines.append(f"Unchanged indexed sources: {unchanged}.")
        lines.append("")
    lines += [
        f"### {ISSUE_HEADINGS[3]}",
        "",
        "Not sure: triage every commit and file above into the triage log of "
        "`upstream/SUPPORTED.md` (ported, not portable and why, or pending).",
        "",
        f"### {ISSUE_HEADINGS[4]}",
        "",
    ]
    rerender = [(n, r) for n, r in ups.items() if r["needs_go_rerender"]]
    for name, rep in rerender:
        lines.append(
            f"- {name}: Go re-render needed ({'; '.join(rep['rerender_reasons'])}): render "
            "`RenderRouting(model.AgentHermes)` into `upstream/odd-routing-hermes.canonical.md` "
            "and diff it against the vendored copy."
        )
    lines.append(
        "- Pending triage. Re-port every changed source before bumping a pin; see "
        '"How to sync with upstream" in `upstream/SUPPORTED.md`.'
    )
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--lock", help="lock file (default: the repository's upstream lock)")
    parser.add_argument("--cache", help=f"upstream checkout directory (env {CACHE_ENV})")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output", help="write the report to this file instead of stdout")
    parser.add_argument("--offline", action="store_true", help="never clone or fetch")
    parser.add_argument("--exit-zero", action="store_true", help="exit 0 on drift (errors exit 2)")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        lock = (
            upstream_lock.load_lock_file(Path(args.lock))
            if args.lock
            else upstream_lock.load_lock()
        )
    except (OSError, ValueError) as exc:
        print(f"check_upstream_drift: cannot load the lock: {exc}", file=sys.stderr)
        return EXIT_ERROR
    report = build_report(lock, resolve_cache(args.cache), offline=args.offline)
    if args.format == "json":
        text = json.dumps(report, indent=2, sort_keys=False) + "\n"
    else:
        text = render_markdown(report)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    for error in report["errors"]:
        print(f"check_upstream_drift: error: {error}", file=sys.stderr)
    return exit_code(report, exit_zero=args.exit_zero)


if __name__ == "__main__":
    sys.exit(main())
