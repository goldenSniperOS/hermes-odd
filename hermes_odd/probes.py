"""Read-only probes of the ``gentle-ai`` binary for ``/odd-status`` and ``/odd-doctor``.

hermes-odd uses the user's installed ``gentle-ai`` binary only; it never runs
``gentle-ai install`` or ``gentle-ai sync`` for Hermes. The probes here run
one read-only subcommand:

* ``gentle-ai version`` (prints ``gentle-ai X.Y.Z``).

Every call runs without a shell, with a minimal environment, stdin closed and
a hard timeout (:data:`PROBE_TIMEOUT_SECONDS`). Results are cached for
:data:`CACHE_TTL_SECONDS` so repeated ``/odd-status`` calls cost nothing.
Nothing here raises.
"""

from __future__ import annotations

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
    stderr = (completed.stderr or "")[:MAX_OUTPUT_CHARS]
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
    """Cached, bounded gentle-ai probes shared by ``/odd-status`` and ``/odd-doctor``."""

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

    def invalidate(self, *kinds: str) -> None:
        with self._lock:
            for key in [k for k in self._cache if k[0] in kinds]:
                del self._cache[key]
