"""
Simple thread-safe in-memory TTL cache for API endpoint responses.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Optional, Tuple


class TTLCache:
    """Fixed-capacity TTL cache backed by a plain dict + lock."""

    def __init__(self, ttl_seconds: float = 30.0, maxsize: int = 256):
        self._ttl = ttl_seconds
        self._maxsize = maxsize
        self._store: dict[str, Tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Tuple[bool, Any]:
        """Return (hit, value). hit=False on miss or expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False, None
            expires_at, value = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return False, None
            return True, value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._store) >= self._maxsize:
                # Evict oldest entry
                oldest = min(self._store.items(), key=lambda kv: kv[1][0])
                del self._store[oldest[0]]
            self._store[key] = (time.monotonic() + self._ttl, value)

    def invalidate(self, key: Optional[str] = None) -> None:
        with self._lock:
            if key is None:
                self._store.clear()
            else:
                self._store.pop(key, None)


# Shared cache instances
country_hotspot_cache = TTLCache(ttl_seconds=30.0)
admin1_hotspot_cache = TTLCache(ttl_seconds=20.0)
city_hotspot_cache = TTLCache(ttl_seconds=20.0)
globe_hotspot_cache = TTLCache(ttl_seconds=25.0)
