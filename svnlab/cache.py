from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

CACHE_FORMAT_VERSION = "v2-decoding"


def default_cache_path() -> Path:
    if local_app_data := os.environ.get("LOCALAPPDATA"):
        root = Path(local_app_data)
    elif xdg_cache_home := os.environ.get("XDG_CACHE_HOME"):
        root = Path(xdg_cache_home)
    else:
        root = Path.home() / ".cache"
    return root / "SVNLab" / "cache.sqlite3"


class RepositoryCache:
    """Persistent cache for immutable SVN responses without credentials."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._initialized = False
        self._initialize_lock = asyncio.Lock()
        self._key_locks = tuple(asyncio.Lock() for _ in range(64))

    @staticmethod
    def key(
        repository: str,
        username: str,
        kind: str,
        *identity: str | int | None,
    ) -> str:
        scope = hashlib.sha256(
            f"{repository.rstrip('/')}\0{username}".encode()
        ).hexdigest()
        detail = "\0".join("" if item is None else str(item) for item in identity)
        return hashlib.sha256(
            f"{CACHE_FORMAT_VERSION}\0{scope}\0{kind}\0{detail}".encode()
        ).hexdigest()

    async def get_or_load_json(
        self,
        key: str,
        loader: Callable[[], Awaitable[dict[str, Any]]],
        *,
        refresh: bool = False,
    ) -> tuple[dict[str, Any], bool]:
        async def load_text() -> str:
            value = await loader()
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

        payload, cache_hit = await self.get_or_load_text(
            key, load_text, refresh=refresh
        )
        try:
            value = json.loads(payload)
        except json.JSONDecodeError:
            await self.delete(key)
            payload, cache_hit = await self.get_or_load_text(
                key, load_text, refresh=True
            )
            value = json.loads(payload)
        if not isinstance(value, dict):
            await self.delete(key)
            payload, cache_hit = await self.get_or_load_text(
                key, load_text, refresh=True
            )
            value = json.loads(payload)
        return value, cache_hit

    async def get_or_load_text(
        self,
        key: str,
        loader: Callable[[], Awaitable[str]],
        *,
        refresh: bool = False,
    ) -> tuple[str, bool]:
        await self._ensure_initialized()
        if not refresh:
            cached = await asyncio.to_thread(self._read, key)
            if cached is not None:
                return cached, True

        lock = self._key_locks[int(key[:8], 16) % len(self._key_locks)]
        async with lock:
            if not refresh:
                cached = await asyncio.to_thread(self._read, key)
                if cached is not None:
                    return cached, True
            value = await loader()
            await asyncio.to_thread(self._write, key, value)
            return value, False

    async def delete(self, key: str) -> None:
        await self._ensure_initialized()
        await asyncio.to_thread(self._delete, key)

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        async with self._initialize_lock:
            if self._initialized:
                return
            await asyncio.to_thread(self._initialize)
            self._initialized = True

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )

    def _read(self, key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM cache_entries WHERE cache_key = ?", (key,)
            ).fetchone()
        return None if row is None else str(row[0])

    def _write(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO cache_entries(cache_key, payload, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload = excluded.payload,
                    created_at = excluded.created_at
                """,
                (key, value, time.time()),
            )

    def _delete(self, key: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM cache_entries WHERE cache_key = ?", (key,))
