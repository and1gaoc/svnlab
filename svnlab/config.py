from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    svn_executable: str = "svn"
    max_svn_processes: int = 4
    info_timeout_seconds: float = 20.0
    log_timeout_seconds: float = 40.0
    diff_timeout_seconds: float = 90.0
    content_timeout_seconds: float = 60.0
    cache_ttl_seconds: float = 300.0
    cache_max_entries: int = 24
    cache_max_bytes: int = 32 * 1024 * 1024


DEFAULT_SETTINGS = Settings()

