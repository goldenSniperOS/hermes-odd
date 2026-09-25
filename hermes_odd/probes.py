"""Read-only probes of the ``gentle-ai`` binary for ``/odd_status`` and ``/odd_doctor``.

hermes-odd uses the user's installed ``gentle-ai`` binary only (RDD through
``gentle-ai review``); it never runs ``gentle-ai install`` or
``gentle-ai sync`` for Hermes. The probes here run exactly three read-only
subcommands:

* ``gentle-ai version`` (prints ``gentle-ai X.Y.Z``);
* ``gentle-ai review mode status [--cwd <repo>] --json`` (schema
  ``gentle-ai.review-mode/v1``; ``status`` is documented as read-only in
  ``gentle-ai review mode --help``);
* ``gentle-ai review status --cwd <git repo> --contract
  gentle-ai.review-integration/v2 --agent hermes --next-transition``: the
  native review availability probe. gentle-ai 3.7.0 refuses it in preflight
  with ``immutable_review_transport_unsupported`` (Hermes is not an eligible
  immutable review runtime). It only runs with ``--cwd`` pointing at an
  existing git repository, because ``review status`` may initialize Git in a
  genuinely unversioned directory once a runtime is accepted.

The identity is always :data:`AGENT_ID` (``hermes``). hermes-odd never
passes another runtime's identity to gentle-ai (never ``--agent pi``): that
would break the review contract and make receipts meaningless.

The only writes are the explicit, user-typed ``/odd_review_mode
enable|disable`` commands (:meth:`Prober.set_review_mode`), which change
gentle-ai's own review switch and nothing else.

Every call runs without a shell, with a minimal environment, stdin closed and
a hard timeout (:data:`PROBE_TIMEOUT_SECONDS`). Results are cached for
:data:`CACHE_TTL_SECONDS` so repeated ``/odd_status`` calls cost nothing.
Nothing here raises.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BINARY_NAME = "gentle-ai"
PROBE_TIMEOUT_SECONDS = 3.0
CACHE_TTL_SECONDS = 60.0
MAX_BINARIES = 5
MAX_OUTPUT_CHARS = 64 * 1024
MUTATION_TIMEOUT_SECONDS = 5.0
MAX_STDERR_CHARS = 4096
REVIEW_MODE_SCHEMA = "gentle-ai.review-mode/v1"
# The only runtime identity hermes-odd ever passes to ``gentle-ai review``.
AGENT_ID = "hermes"
REVIEW_CONTRACT = "gentle-ai.review-integration/v2"
REVIEW_FAILURE_SCHEMA = "gentle-ai.review-integration.failure/v2"
UNSUPPORTED_CODE = "immutable_review_transport_unsupported"
REVIEW_MODE_ACTIONS = ("status", "enable", "disable")
REVIEW_MODE_SCOPES = ("global", "clone")
_RUNTIMES_RE = re.compile(r"supported immutable review runtimes:\s*([^;\n\"]*)")
_RUNTIME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_CODE_RE = re.compile(r"^[a-z0-9_.-]{1,80}$")
MAX_RUNTIMES = 10
_VERSION_RE = re.compile(r"\bv?(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?\b")


@dataclass(frozen=True)
class ProbeResult:
    """Outcome of one subprocess run."""

    state: str  # "ok" | "timeout" | "failed" | "missing"
    stdout: str = ""
    returncode: int | None = None
    stderr: str = ""


@dataclass(frozen=True)
class BinaryInfo:
    path: str
    version: str | None  # "3.7.0" when parsed
    state: str  # "ok" | "timeout" | "failed" | "unparsed"


@dataclass(frozen=True)
class ReviewMode:
    state: str  # "ok" | "no_repo" | "no_binary" | "timeout" | "failed"
    effective: str = ""  # "on" | "off"
    source: str = ""  # "global" | "clone" | ...
    repo: str = ""
    global_mode: str = ""  # "on" | "off" | "" (unset)
    clone_local: str = ""  # "off" | "" (unset)


@dataclass(frozen=True)
class NativeReview:
    """Whether ``gentle-ai review`` accepts Hermes as an immutable review runtime."""

    state: str  # "unavailable" | "available" | "unknown" | "timeout" | "no_binary" | "no_repo"
    code: str = ""  # gentle-ai failure code, when one was reported
    runtimes: tuple[str, ...] = ()  # runtimes gentle-ai names as eligible
    detail: str = ""


def review_mode_command(
    binary: str, action: str, scope: str | None = None, repo: str | Path | None = None
) -> list[str]:
    """argv for ``gentle-ai review mode <action>``. ``enable``/``disable`` need an
    explicit ``scope``; there is never an ``--agent`` flag."""
    if action not in REVIEW_MODE_ACTIONS:
        raise ValueError(f"unknown review mode action {action!r}")
    command = [binary, "review", "mode", action]
    if action != "status":
        if scope not in REVIEW_MODE_SCOPES:
            raise ValueError("enable/disable need an explicit scope: global or clone")
        command += ["--scope", scope]
    if repo is not None:
        command += ["--cwd", str(repo)]
    command.append("--json")
    return command


def native_review_command(binary: str, repo: str | Path) -> list[str]:
    """argv of the read-only availability probe, always as ``--agent hermes``."""
    return [
        binary,
        "review",
        "status",
        "--cwd",
        str(repo),
        "--contract",
        REVIEW_CONTRACT,
        "--agent",
        AGENT_ID,
        "--next-transition",
    ]


Runner = Callable[[list[str], float], ProbeResult]


def parse_version(text: Any) -> tuple[int, int, int] | None:
    """``"gentle-ai 3.7.0"`` -> ``(3, 7, 0)``; ``None`` when absent."""
    match = _VERSION_RE.search(str(text or ""))
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def version_text(version: tuple[int, int, int] | None) -> str | None:
    return ".".join(str(p) for p in version) if version else None


def is_below(version: str | None, minimum: str | None) -> bool | None:
    """Whether ``version`` is below ``minimum``; ``None`` when either is unknown."""
    have, need = parse_version(version), parse_version(minimum)
    if have is None or need is None:
        return None
    return have < need


def probe_env(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Minimal environment: ``PATH``, ``HOME`` (gentle-ai reads its own config
    there), ``LC_ALL=C`` and no colors. Nothing else is inherited."""
    env_in = os.environ if environ is None else environ
    env = {"PATH": env_in.get("PATH", "/usr/bin:/bin"), "LC_ALL": "C", "NO_COLOR": "1"}
    home = env_in.get("HOME")
    if home:
        env["HOME"] = home
    return env


def run_probe(command: list[str], timeout: float) -> ProbeResult:
    """Run ``command`` without a shell under a hard timeout. Never raises."""
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=max(0.1, timeout),
            env=probe_env(),
            stdin=subprocess.DEVNULL,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return ProbeResult("timeout")
    except FileNotFoundError:
        return ProbeResult("missing")
    except (OSError, ValueError, subprocess.SubprocessError):
        return ProbeResult("failed")
    stdout = (completed.stdout or "")[:MAX_OUTPUT_CHARS]
    stderr = (completed.stderr or "")[:MAX_STDERR_CHARS]
    state = "ok" if completed.returncode == 0 else "failed"
    return ProbeResult(state, stdout, completed.returncode, stderr)


def find_binaries(
    environ: Mapping[str, str] | None = None,
    which: Callable[..., str | None] = shutil.which,
    is_executable: Callable[[str], bool] | None = None,
) -> list[str]:
    """Every ``gentle-ai`` on ``PATH``, first-on-PATH first, deduplicated by
    real path (a Homebrew symlink and its Cellar target count once)."""
    env = os.environ if environ is None else environ
    path_var = env.get("PATH", "")
    check = is_executable or (lambda p: os.path.isfile(p) and os.access(p, os.X_OK))
    found: list[str] = []
    seen: set[str] = set()

    def add(candidate: str | None) -> None:
        if not candidate:
            return
        try:
            key = os.path.realpath(candidate)
        except (OSError, ValueError):
            key = candidate
        if key in seen:
            return
        seen.add(key)
        found.append(candidate)

    try:
        add(which(BINARY_NAME, path=path_var))
    except Exception:  # noqa: BLE001 - which is best effort
        pass
    for directory in path_var.split(os.pathsep):
        if not directory or len(found) >= MAX_BINARIES:
            continue
        candidate = os.path.join(directory, BINARY_NAME)
        try:
            if check(candidate):
                add(candidate)
        except Exception:  # noqa: BLE001
            continue
    return found[:MAX_BINARIES]


def git_repo_root(start: str | Path | None) -> Path | None:
    """Nearest ancestor of ``start`` holding ``.git`` (no subprocess), else ``None``."""
    if not start:
        return None
    try:
        path = Path(start).expanduser()
        if not path.is_absolute() or not path.is_dir():
            return None
        current = path.resolve()
        for _ in range(64):
            if (current / ".git").exists():
                return current
            if current.parent == current:
                return None
            current = current.parent
    except (OSError, RuntimeError, ValueError):
        return None
    return None


def process_repo(environ: Mapping[str, str] | None = None) -> Path | None:
    """The git repository of the command process: ``TERMINAL_CWD`` first (the
    CLI exports its launch directory), then ``os.getcwd()``."""
    env = os.environ if environ is None else environ
    candidates = [str(env.get("TERMINAL_CWD", "") or "").strip()]
    try:
        candidates.append(os.getcwd())
    except OSError:
        pass
    for candidate in candidates:
        root = git_repo_root(candidate)
        if root is not None:
            return root
    return None


class Prober:
    """Cached, bounded gentle-ai probes shared by ``/odd_status`` and ``/odd_doctor``."""

    def __init__(
        self,
        runner: Runner = run_probe,
        clock: Callable[[], float] = time.monotonic,
        ttl: float = CACHE_TTL_SECONDS,
        finder: Callable[[], list[str]] | None = None,
    ):
        self._runner = runner
        self._clock = clock
        self._ttl = ttl
        self._finder = finder or find_binaries
        self._cache: dict[tuple, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self.runs = 0  # subprocess runs (for tests)

    def _cached(self, key: tuple) -> Any:
        with self._lock:
            hit = self._cache.get(key)
            if hit is not None and self._clock() - hit[0] < self._ttl:
                return hit[1]
        return None

    def _store(self, key: tuple, value: Any) -> Any:
        with self._lock:
            self._cache[key] = (self._clock(), value)
        return value

    def peek(self, key: tuple) -> Any:
        """Cached value or ``None``; never probes."""
        return self._cached(key)

    def _run(self, command: list[str], timeout: float) -> ProbeResult:
        self.runs += 1
        try:
            result = self._runner(command, timeout)
        except Exception:  # noqa: BLE001 - never raise
            return ProbeResult("failed")
        return result if isinstance(result, ProbeResult) else ProbeResult("failed")

    def binaries(self) -> list[str]:
        key = ("binaries",)
        hit = self._cached(key)
        if hit is not None:
            return list(hit)
        try:
            found = list(self._finder())
        except Exception:  # noqa: BLE001
            found = []
        return list(self._store(key, found))

    def version(self, path: str, timeout: float = PROBE_TIMEOUT_SECONDS) -> BinaryInfo:
        key = ("version", path)
        hit = self._cached(key)
        if hit is not None:
            return hit
        result = self._run([path, "version"], min(timeout, PROBE_TIMEOUT_SECONDS))
        if result.state != "ok":
            info = BinaryInfo(path, None, result.state)
        else:
            parsed = version_text(parse_version(result.stdout))
            info = BinaryInfo(path, parsed, "ok" if parsed else "unparsed")
        return self._store(key, info)

    def versions(
        self, paths: list[str], timeout: float = PROBE_TIMEOUT_SECONDS
    ) -> list[BinaryInfo]:
        """Probe every path concurrently so the total stays within one timeout."""
        if not paths:
            return []
        if len(paths) == 1:
            return [self.version(paths[0], timeout)]
        with ThreadPoolExecutor(max_workers=min(len(paths), MAX_BINARIES)) as pool:
            return list(pool.map(lambda p: self.version(p, timeout), paths))

    def first_version(self) -> BinaryInfo | None:
        """First-on-PATH binary and its version (cached), or ``None`` when missing."""
        paths = self.binaries()
        return self.version(paths[0]) if paths else None

    def review_mode(
        self,
        binary: str | None,
        repo: Path | None,
        timeout: float = PROBE_TIMEOUT_SECONDS,
    ) -> ReviewMode:
        if repo is None:
            return ReviewMode("no_repo")
        if not binary:
            return ReviewMode("no_binary", repo=str(repo))
        key = ("review_mode", binary, str(repo))
        hit = self._cached(key)
        if hit is not None:
            return hit
        command = review_mode_command(binary, "status", repo=repo)
        result = self._run(command, min(timeout, PROBE_TIMEOUT_SECONDS))
        return self._store(key, parse_review_mode(result, str(repo)))

    def global_review_mode(
        self, binary: str | None, timeout: float = PROBE_TIMEOUT_SECONDS
    ) -> ReviewMode:
        """``review mode status --json`` without ``--cwd``: only for a command
        process that is not inside a git repository (gentle-ai then reports the
        global source alone)."""
        if not binary:
            return ReviewMode("no_binary")
        key = ("review_mode_global", binary)
        hit = self._cached(key)
        if hit is not None:
            return hit
        result = self._run(
            review_mode_command(binary, "status"), min(timeout, PROBE_TIMEOUT_SECONDS)
        )
        return self._store(key, parse_review_mode(result, ""))

    def native_review(
        self,
        binary: str | None,
        repo: Path | None,
        timeout: float = PROBE_TIMEOUT_SECONDS,
    ) -> NativeReview:
        """Probe whether gentle-ai accepts ``--agent hermes`` for native review.

        Runtime eligibility does not depend on the repository, so the result
        is cached per binary. ``repo`` must lie inside an existing git
        repository (the probe is never run elsewhere)."""
        if not binary:
            return NativeReview("no_binary")
        key = ("native_review", binary)
        hit = self._cached(key)
        if hit is not None:
            return hit
        if repo is None or git_repo_root(repo) is None:
            return NativeReview("no_repo")
        result = self._run(native_review_command(binary, repo), min(timeout, PROBE_TIMEOUT_SECONDS))
        return self._store(key, parse_native_review(result))

    def cached_native_review(self) -> NativeReview | None:
        """Any fresh native review result (runtime eligibility is per binary)."""
        with self._lock:
            now = self._clock()
            for key, (at, value) in self._cache.items():
                if key[0] == "native_review" and now - at < self._ttl:
                    return value
        return None

    def set_review_mode(
        self,
        binary: str,
        action: str,
        scope: str,
        repo: Path | None,
        timeout: float = MUTATION_TIMEOUT_SECONDS,
    ) -> tuple[ReviewMode, ProbeResult]:
        """Run ``gentle-ai review mode enable|disable --scope <scope> [--cwd
        <repo>] --json`` once, never cached, and drop cached review modes.

        Only called for an explicit user-typed ``/odd_review_mode`` command."""
        if action not in ("enable", "disable"):
            raise ValueError(f"not a review mode write: {action!r}")
        command = review_mode_command(binary, action, scope, repo)
        result = self._run(command, min(timeout, MUTATION_TIMEOUT_SECONDS))
        self.invalidate("review_mode", "review_mode_global")
        parsed = parse_review_mode(
            ProbeResult("ok", result.stdout, result.returncode, result.stderr)
            if result.state in ("ok", "failed")
            else result,
            str(repo) if repo is not None else "",
        )
        return parsed, result

    def invalidate(self, *kinds: str) -> None:
        with self._lock:
            for key in [k for k in self._cache if k[0] in kinds]:
                del self._cache[key]

    def cached_review_mode(self, repo: Path | None) -> ReviewMode | None:
        """A review-mode result cached by ``/odd_doctor`` for ``repo``, if fresh."""
        if repo is None:
            return None
        with self._lock:
            now = self._clock()
            for key, (at, value) in self._cache.items():
                if key[0] == "review_mode" and key[2] == str(repo) and now - at < self._ttl:
                    return value
        return None


def parse_review_mode(result: ProbeResult, repo: str) -> ReviewMode:
    if result.state != "ok":
        return ReviewMode(result.state if result.state == "timeout" else "failed", repo=repo)
    try:
        data = json.loads(result.stdout)
    except ValueError:
        return ReviewMode("failed", repo=repo)
    status = data.get("status") if isinstance(data, dict) else None
    if (
        not isinstance(data, dict)
        or data.get("schema") != REVIEW_MODE_SCHEMA
        or not isinstance(status, dict)
    ):
        return ReviewMode("failed", repo=repo)
    effective = status.get("effective")
    if effective not in ("on", "off"):
        return ReviewMode("failed", repo=repo)
    source = status.get("source")

    def text(value: Any) -> str:
        return value if value in ("on", "off") else ""

    return ReviewMode(
        "ok",
        effective,
        source[:20] if isinstance(source, str) else "",
        repo,
        text(status.get("global")),
        text(status.get("clone_local")),
    )


def _json_object(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    for candidate in (raw, raw[raw.find("{") : raw.rfind("}") + 1] if "{" in raw else ""):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
        except ValueError:
            continue
        return data if isinstance(data, dict) else None
    return None


def parse_runtimes(cause: Any) -> tuple[str, ...]:
    """Eligible runtimes named in a gentle-ai failure ``cause``."""
    match = _RUNTIMES_RE.search(str(cause or ""))
    if not match:
        return ()
    names = []
    for item in match.group(1).split(","):
        name = item.strip().lower()
        if _RUNTIME_RE.fullmatch(name) and name not in names:
            names.append(name)
    return tuple(names[:MAX_RUNTIMES])


def parse_native_review(result: ProbeResult) -> NativeReview:
    """Classify the availability probe. Never raises.

    * failure schema + ``immutable_review_transport_unsupported`` -> unavailable;
    * exit 0 with a non-failure JSON object -> available (detected);
    * any other failure code -> unknown, with that code;
    * anything else (timeout, missing binary, garbage) -> unknown / timeout.
    """
    if result.state == "timeout":
        return NativeReview("timeout")
    if result.state == "missing":
        return NativeReview("no_binary")
    data = _json_object(result.stdout)
    if data is None:
        return NativeReview("unknown", detail="unreadable gentle-ai output")
    schema = data.get("schema")
    raw_code = data.get("code")
    code = raw_code if isinstance(raw_code, str) and _CODE_RE.fullmatch(raw_code) else ""
    if schema == REVIEW_FAILURE_SCHEMA:
        if code == UNSUPPORTED_CODE:
            return NativeReview("unavailable", code, parse_runtimes(data.get("cause")))
        return NativeReview("unknown", code, detail="gentle-ai refused the probe")
    if result.state == "ok" and isinstance(schema, str) and schema:
        return NativeReview("available", detail=schema[:80])
    return NativeReview("unknown", code, detail="unexpected gentle-ai output")
