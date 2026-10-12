from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .cache import default_cache_path


@dataclass(frozen=True, slots=True)
class Settings:
    svn_executable: str = "svn"
    max_svn_processes: int = 4
    info_timeout_seconds: float = 60.0
    log_timeout_seconds: float = 180.0
    diff_timeout_seconds: float = 600.0
    content_timeout_seconds: float = 300.0
    cache_path: Path = field(default_factory=default_cache_path)


DEFAULT_SETTINGS = Settings()

