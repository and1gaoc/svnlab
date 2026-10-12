from __future__ import annotations

import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

SUPPORTED_SCHEMES = {"file", "http", "https", "svn", "svn+ssh"}


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RepositoryConnection(ApiModel):
    repository: str = Field(min_length=1, max_length=2048)
    username: str = Field(default="", max_length=512)
    password: str = Field(default="", max_length=2048)

    @field_validator("repository")
    @classmethod
    def validate_repository(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in SUPPORTED_SCHEMES:
            allowed = ", ".join(sorted(SUPPORTED_SCHEMES))
            raise ValueError(f"repository must use one of: {allowed}")
        if parsed.scheme != "file" and not parsed.netloc:
            raise ValueError("repository URL must include a host")
        if any(char in value for char in ("\r", "\n", "\x00")):
            raise ValueError("repository contains unsupported characters")
        return value.rstrip("/")


class RepositoryRequest(ApiModel):
    connection: RepositoryConnection


class CommitListRequest(RepositoryRequest):
    limit: int = Field(default=30, ge=1, le=100)
    before_revision: int | None = Field(default=None, ge=1)
    refresh: bool = False


class FileContentRequest(RepositoryRequest):
    path: str = Field(min_length=1, max_length=4096)
    revision: int = Field(ge=0)
    start_line: int = Field(default=1, ge=1)
    line_count: int = Field(default=100, ge=1, le=500)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if any(char in value for char in ("\r", "\n", "\x00")):
            raise ValueError("path contains unsupported characters")
        return value


class ChangedPath(ApiModel):
    path: str
    action: Literal["A", "D", "M", "R", "?"] = "?"
    kind: str | None = None
    copy_from_path: str | None = None
    copy_from_revision: int | None = None


class Commit(ApiModel):
    revision: int
    author: str
    date: str
    message: str
    changed_paths: list[ChangedPath] = Field(default_factory=list)

    @property
    def changed_file_count(self) -> int:
        return len(self.changed_paths)


class DiffLine(ApiModel):
    kind: Literal["context", "addition", "deletion", "meta"]
    content: str
    old_line: int | None = None
    new_line: int | None = None


class DiffHunk(ApiModel):
    header: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[DiffLine] = Field(default_factory=list)


class DiffFile(ApiModel):
    path: str
    old_path: str | None = None
    new_path: str | None = None
    status: Literal["added", "deleted", "modified", "replaced", "property", "binary", "unknown"] = "modified"
    binary: bool = False
    hunks: list[DiffHunk] = Field(default_factory=list)
    property_changes: list[str] = Field(default_factory=list)
    raw_fallback: list[str] = Field(default_factory=list)


class ErrorEnvelope(ApiModel):
    error: str
    message: str
    hint: str | None = None


class ContentRange(ApiModel):
    path: str
    revision: int
    start_line: int
    end_line: int
    total_lines: int
    has_before: bool
    has_after: bool
    lines: list[str]


HUNK_HEADER_RE = re.compile(
    r"^@@\s+-(?P<old_start>\d+)(?:,(?P<old_count>\d+))?\s+"
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))?\s+@@"
)

