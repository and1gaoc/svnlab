from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi import Path as ApiPath

from .cache import SourceCache
from .models import CommitListRequest, FileContentRequest, RepositoryRequest
from .svn_client import SvnClient

router = APIRouter(prefix="/api")


def _client(request: Request) -> SvnClient:
    return request.app.state.svn_client


def _cache(request: Request) -> SourceCache:
    return request.app.state.source_cache


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    client = _client(request)
    executable = client.settings.svn_executable
    return {
        "status": "ok",
        "service": "svnlab",
        "svn_executable": executable,
        "svn_available": bool(shutil.which(executable) or Path(executable).is_file()),
    }


@router.post("/repository/check")
async def check_repository(payload: RepositoryRequest, request: Request) -> dict[str, object]:
    info = await _client(request).info(payload.connection)
    return {"ok": True, "repository": info}


@router.post("/commits")
async def list_commits(payload: CommitListRequest, request: Request) -> dict[str, object]:
    commits = await _client(request).commits(
        payload.connection,
        limit=payload.limit,
        before_revision=payload.before_revision,
    )
    items = []
    for commit in commits:
        item = commit.model_dump()
        item["changed_file_count"] = commit.changed_file_count
        items.append(item)
    next_before = commits[-1].revision - 1 if len(commits) == payload.limit else None
    return {"commits": items, "next_before": next_before}


@router.post("/commits/{revision}")
async def revision_detail(
    payload: RepositoryRequest,
    request: Request,
    revision: int = ApiPath(ge=1),
) -> dict[str, object]:
    commit, diffs = await _client(request).revision(payload.connection, revision)
    _merge_changed_path_status(commit.changed_paths, diffs)
    known = {_normal_path(diff.path) for diff in diffs}
    for changed in commit.changed_paths:
        relative = changed.path.lstrip("/")
        if not any(
            relative == path or relative.endswith(f"/{path}") or path.endswith(f"/{relative}")
            for path in known
        ):
            from .models import DiffFile

            status = {
                "A": "added",
                "D": "deleted",
                "R": "replaced",
                "M": "property",
            }.get(changed.action, "unknown")
            diffs.append(DiffFile(path=relative, status=status))

    item = commit.model_dump()
    item["changed_file_count"] = commit.changed_file_count
    return {
        "revision": item,
        "diffs": [diff.model_dump() for diff in diffs],
    }


@router.post("/files/content")
async def file_content(payload: FileContentRequest, request: Request) -> dict[str, object]:
    cache = _cache(request)
    cache_key = "\x1f".join(
        (
            payload.connection.repository,
            payload.connection.username,
            str(payload.revision),
            payload.path,
        )
    )

    async def load() -> str:
        return await _client(request).file_text(
            payload.connection, payload.path, payload.revision
        )

    lines = await cache.get_or_load(cache_key, load)
    total = len(lines)
    start = min(payload.start_line, total + 1)
    selected = lines[start - 1 : start - 1 + payload.line_count]
    end = start + len(selected) - 1 if selected else min(total, start - 1)
    return {
        "path": payload.path,
        "revision": payload.revision,
        "start_line": start,
        "end_line": end,
        "total_lines": total,
        "has_before": start > 1,
        "has_after": end < total,
        "lines": selected,
    }


def _normal_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("/")


def _merge_changed_path_status(changed_paths: list, diffs: list) -> None:
    for diff in diffs:
        normalized = _normal_path(diff.path)
        match = next(
            (
                item
                for item in changed_paths
                if _normal_path(item.path) == normalized
                or _normal_path(item.path).endswith(f"/{normalized}")
            ),
            None,
        )
        if match is None:
            continue
        diff.status = {
            "A": "added",
            "D": "deleted",
            "R": "replaced",
            "M": diff.status,
        }.get(match.action, diff.status)

