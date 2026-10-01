"""Read-only view of the optional ``recall`` memory provider (hermes-recall).

hermes-recall is a separate, exclusive Hermes plugin (an Engram-compatible
``MemoryProvider``). hermes-odd never imports it and never writes anything it
owns. This module only reads:

* the global Hermes config, through Hermes' own cached
  ``hermes_cli.config.load_config_readonly`` (``memory.provider`` and whether
  an ``mcp_servers.engram`` entry exists). Outside Hermes the config is
  unknown (``None``); this plugin parses no YAML.
* the provider's state file ``<hermes_home>/recall/state.json``, whose schema
  is frozen and owned by hermes-recall:
  ``{"last_memory_id": int, "last_action": str, "project": str,
  "updated_at": ISO-8601 str}``.
* Engram's ``GET /health``, capped at :data:`HEALTH_TIMEOUT_SECONDS` and
  cached for :data:`HEALTH_CACHE_TTL_SECONDS` (like :class:`hermes_odd.probes.Prober`).

Nothing here raises: every failure degrades to ``None`` or ``ok=False``.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import soul as soul_mod

PROVIDER_RECALL = "recall"
ENGRAM_DEFAULT_URL = "http://127.0.0.1:7437"
HEALTH_TIMEOUT_SECONDS = 1.5
HEALTH_CACHE_TTL_SECONDS = 30.0
MAX_STATE_BYTES = 64 * 1024
MAX_HEALTH_BYTES = 8 * 1024

ConfigSource = Callable[[], Mapping[str, Any] | None]
Opener = Callable[[str, float], bytes]  # (health URL, timeout) -> body


@dataclass(frozen=True)
class LastMemory:
    """The last memory hermes-recall recorded, as written in its state file."""

    memory_id: int
    action: str
    project: str
    updated_at: str  # raw ISO-8601 string


@dataclass(frozen=True)
class RecallInfo:
    """Config + state snapshot for ``/odd-status`` and ``/odd-doctor``."""

    provider: str | None  # None: config unknown; "": builtin memory only
    engram_mcp_configured: bool
    last: LastMemory | None

    @property
    def active(self) -> bool:
        return self.provider == PROVIDER_RECALL


@dataclass(frozen=True)
class EngramHealth:
    ok: bool
    reason: str = ""  # "unreachable" | "timeout" | "bad response" | "not ok"
    version: str | None = None


def read_state(home: Path | str | None) -> LastMemory | None:
    """Parse ``<home>/recall/state.json``; ``None`` on any problem."""
    try:
        path = Path(home) / "recall" / "state.json"
        if not path.is_file() or path.stat().st_size > MAX_STATE_BYTES:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        memory_id = data["last_memory_id"]
        fields = (data["last_action"], data["project"], data["updated_at"])
    except Exception:  # noqa: BLE001 - missing, unreadable, malformed or not a dict
        return None
    if isinstance(memory_id, bool) or not isinstance(memory_id, int):
        return None
    if not all(isinstance(value, str) for value in fields):
        return None
    return LastMemory(memory_id, *fields)


def load_global_config() -> Mapping[str, Any] | None:
    """Hermes' cached global config (read-only, never mutate), else ``None``."""
    try:
        from hermes_cli.config import load_config_readonly

        config = load_config_readonly()
    except Exception:  # noqa: BLE001 - not running inside Hermes, or it failed
        return None
    return config if isinstance(config, Mapping) else None


def provider_of(config: Mapping[str, Any] | None) -> str | None:
    """``memory.provider`` lowercased; ``""`` when set empty, ``None`` when unknown."""
    try:
        memory = config.get("memory") if isinstance(config, Mapping) else None
        if not isinstance(memory, Mapping) or "provider" not in memory:
            return None
        value = memory.get("provider")
    except Exception:  # noqa: BLE001 - a hostile mapping must not break status
        return None
    if value is None:
        return ""
    return value.strip().lower() if isinstance(value, str) else None


def engram_mcp_configured(config: Mapping[str, Any] | None) -> bool:
    """Whether the config declares an ``mcp_servers.engram`` entry."""
    try:
        servers = config.get("mcp_servers") if isinstance(config, Mapping) else None
        return isinstance(servers, Mapping) and "engram" in servers
    except Exception:  # noqa: BLE001
        return False


def age_text(updated_at: str, now: float) -> str:
    """``"just now"``, ``"3m ago"``, ``"2h ago"`` or ``"5d ago"``; ``""`` if unparsable.

    A timestamp without an offset is read as UTC; a future one is "just now".
    """
    try:
        moment = datetime.fromisoformat(str(updated_at).strip().replace("Z", "+00:00"))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        delta = float(now) - moment.timestamp()
    except Exception:  # noqa: BLE001
        return ""
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if delta >= size:
            return f"{int(delta // size)}{unit} ago"
    return "just now"


def engram_url(environ: Mapping[str, str] | None = None) -> str:
    """``ENGRAM_URL`` when set and non-empty, else :data:`ENGRAM_DEFAULT_URL`."""
    env = os.environ if environ is None else environ
    value = str(env.get("ENGRAM_URL", "") or "").strip().rstrip("/")
    return value or ENGRAM_DEFAULT_URL


def fetch_health(url: str, timeout: float) -> bytes:
    """Default opener: ``GET url`` (http/https only); raises on transport errors."""
    if not url.startswith(("http://", "https://")):
        raise ValueError("unsupported scheme")
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read(MAX_HEALTH_BYTES)


def _classify(body: Any) -> EngramHealth:
    try:
        data = json.loads(bytes(body).decode("utf-8"))
    except Exception:  # noqa: BLE001
        return EngramHealth(False, "bad response")
    if not isinstance(data, Mapping):
        return EngramHealth(False, "bad response")
    version = data.get("version")
    version = version if isinstance(version, str) and version else None
    if data.get("status") == "ok":
        return EngramHealth(True, "", version)
    return EngramHealth(False, "not ok", version)


def engram_health(base_url: str, opener: Opener = fetch_health) -> EngramHealth:
    """One uncached ``GET <base_url>/health`` probe. Never raises."""
    try:
        body = opener(f"{base_url.rstrip('/')}/health", HEALTH_TIMEOUT_SECONDS)
    except TimeoutError:
        return EngramHealth(False, "timeout")
    except urllib.error.URLError as exc:
        timed_out = isinstance(exc.reason, TimeoutError)
        return EngramHealth(False, "timeout" if timed_out else "unreachable")
    except Exception:  # noqa: BLE001 - refused, bad scheme, anything the opener raises
        return EngramHealth(False, "unreachable")
    return _classify(body)


class Recall:
    """Fail-soft recall view with a TTL-cached health probe."""

    def __init__(
        self,
        *,
        home: Callable[[], Path] = soul_mod.hermes_home,
        config_source: ConfigSource = load_global_config,
        opener: Opener = fetch_health,
        environ: Mapping[str, str] | None = None,
        clock: Callable[[], float] = time.monotonic,
        ttl: float = HEALTH_CACHE_TTL_SECONDS,
    ) -> None:
        self._home = home
        self._config_source = config_source
        self._opener = opener
        self._environ = environ
        self._clock = clock
        self._ttl = ttl
        self._cache: dict[str, tuple[float, EngramHealth]] = {}
        self._lock = threading.Lock()
        self.probes = 0  # real health probes (for tests)

    def info(self) -> RecallInfo:
        """Provider, Engram MCP wiring and last memory. Never raises."""
        try:
            config = self._config_source()
        except Exception:  # noqa: BLE001
            config = None
        try:
            last = read_state(self._home())
        except Exception:  # noqa: BLE001 - home resolution failed
            last = None
        return RecallInfo(provider_of(config), engram_mcp_configured(config), last)

    def url(self) -> str:
        try:
            return engram_url(self._environ)
        except Exception:  # noqa: BLE001
            return ENGRAM_DEFAULT_URL

    def health(self) -> EngramHealth:
        """``GET /health`` on :meth:`url`, cached per URL for ``ttl`` seconds."""
        url = self.url()
        with self._lock:
            hit = self._cache.get(url)
            if hit is not None and self._clock() - hit[0] < self._ttl:
                return hit[1]
        self.probes += 1
        result = engram_health(url, self._opener)
        with self._lock:
            self._cache[url] = (self._clock(), result)
        return result
