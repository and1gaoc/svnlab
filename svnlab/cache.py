from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass(slots=True)
class _CacheEntry:
    lines: list[str]
    size: int
    expires_at: float


class SourceCache:
    def __init__(self, *, ttl_seconds: float, max_entries: int, max_bytes: int) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self._items: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._bytes = 0
        self._lock = asyncio.Lock()

    async def get_or_load(
        self, key: str, loader: Callable[[], Awaitable[str]]
    ) -> list[str]:
        now = time.monotonic()
        async with self._lock:
            entry = self._items.get(key)
            if entry is not None and entry.expires_at > now:
                self._items.move_to_end(key)
                return entry.lines
            if entry is not None:
                self._remove(key)

        content = await loader()
        lines = content.splitlines()
        if content.endswith(("\n", "\r")):
            lines.append("")
        size = len(content.encode("utf-8"))
        if size > self.max_bytes:
            return lines

        async with self._lock:
            self._evict_expired(now)
            while self._items and (
                len(self._items) >= self.max_entries or self._bytes + size > self.max_bytes
            ):
                _, removed = self._items.popitem(last=False)
                self._bytes -= removed.size
            self._items[key] = _CacheEntry(
                lines=lines, size=size, expires_at=now + self.ttl_seconds
            )
            self._bytes += size
        return lines

    def _evict_expired(self, now: float) -> None:
        expired = [key for key, entry in self._items.items() if entry.expires_at <= now]
        for key in expired:
            self._remove(key)

    def _remove(self, key: str) -> None:
        entry = self._items.pop(key, None)
        if entry is not None:
            self._bytes -= entry.size

