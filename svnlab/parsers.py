from __future__ import annotations

import xml.etree.ElementTree as ET

from .models import HUNK_HEADER_RE, ChangedPath, Commit, DiffFile, DiffHunk, DiffLine


def parse_info_xml(payload: str | bytes) -> dict[str, str | int | None]:
    root = ET.fromstring(payload)
    entry = root.find("entry")
    if entry is None:
        raise ValueError("SVN info response did not contain an entry")
    repository = entry.find("repository")
    return {
        "revision": int(entry.attrib.get("revision", "0")),
        "kind": entry.attrib.get("kind"),
        "url": _text(entry.find("url")),
        "repository_root": _text(repository.find("root"))
        if repository is not None
        else "",
        "repository_uuid": _text(repository.find("uuid"))
        if repository is not None
        else "",
    }


def parse_log_xml(payload: str | bytes) -> list[Commit]:
    root = ET.fromstring(payload)
    commits: list[Commit] = []
    for entry in root.findall("logentry"):
        changed_paths: list[ChangedPath] = []
        paths = entry.find("paths")
        if paths is not None:
            for path_node in paths.findall("path"):
                action = path_node.attrib.get("action", "?")
                if action not in {"A", "D", "M", "R"}:
                    action = "?"
                copy_revision = path_node.attrib.get("copyfrom-rev")
                changed_paths.append(
                    ChangedPath(
                        path=_text(path_node),
                        action=action,
                        kind=path_node.attrib.get("kind"),
                        copy_from_path=path_node.attrib.get("copyfrom-path"),
                        copy_from_revision=int(copy_revision)
                        if copy_revision
                        else None,
                    )
                )
        commits.append(
            Commit(
                revision=int(entry.attrib["revision"]),
                author=_text(entry.find("author")) or "(unknown)",
                date=_text(entry.find("date")),
                message=_text(entry.find("msg")),
                changed_paths=changed_paths,
            )
        )
    return commits


def parse_svn_diff(payload: str) -> list[DiffFile]:
    lines = payload.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    sections: list[tuple[str, list[str]]] = []
    current_path: str | None = None
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("Index: "):
            if current_path is not None:
                sections.append((current_path, current_lines))
            current_path = line[7:].strip()
            current_lines = []
            continue
        if current_path is None and line.startswith("Property changes on: "):
            current_path = line[len("Property changes on: ") :].strip()
        if current_path is not None:
            current_lines.append(line)
    if current_path is not None:
        sections.append((current_path, current_lines))

    return [_parse_diff_section(path, section) for path, section in sections]


def _parse_diff_section(path: str, lines: list[str]) -> DiffFile:
    old_path: str | None = None
    new_path: str | None = None
    binary = False
    hunks: list[DiffHunk] = []
    property_changes: list[str] = []
    fallback: list[str] = []
    in_properties = False
    current_hunk: DiffHunk | None = None
    old_line = 0
    new_line = 0
    old_missing = False
    new_missing = False

    for line in lines:
        if line.startswith("Property changes on: "):
            in_properties = True
            property_changes.append(line)
            current_hunk = None
            continue
        if in_properties:
            property_changes.append(line)
            continue
        if (
            "Cannot display:" in line
            or "is a binary type" in line
            or "Binary files" in line
        ):
            binary = True
            fallback.append(line)
            continue
        if line.startswith("--- "):
            old_missing = "(nonexistent)" in line
            old_path = line[4:].split("\t", 1)[0].strip()
            continue
        if line.startswith("+++ "):
            new_missing = "(nonexistent)" in line
            new_path = line[4:].split("\t", 1)[0].strip()
            continue

        match = HUNK_HEADER_RE.match(line)
        if match:
            old_line = int(match.group("old_start"))
            new_line = int(match.group("new_start"))
            current_hunk = DiffHunk(
                header=line,
                old_start=old_line,
                old_count=int(match.group("old_count") or "1"),
                new_start=new_line,
                new_count=int(match.group("new_count") or "1"),
                lines=[],
            )
            hunks.append(current_hunk)
            continue

        if current_hunk is not None:
            if line.startswith("+") and not line.startswith("+++"):
                current_hunk.lines.append(
                    DiffLine(kind="addition", content=line[1:], new_line=new_line)
                )
                new_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                current_hunk.lines.append(
                    DiffLine(kind="deletion", content=line[1:], old_line=old_line)
                )
                old_line += 1
            elif line.startswith(" "):
                current_hunk.lines.append(
                    DiffLine(
                        kind="context",
                        content=line[1:],
                        old_line=old_line,
                        new_line=new_line,
                    )
                )
                old_line += 1
                new_line += 1
            elif line.startswith("\\"):
                current_hunk.lines.append(DiffLine(kind="meta", content=line))
            elif line:
                fallback.append(line)
            continue

        if line and not set(line) <= {"_", "="}:
            fallback.append(line)

    if binary:
        status = "binary"
    elif old_missing:
        status = "added"
    elif new_missing:
        status = "deleted"
    elif property_changes and not hunks:
        status = "property"
    else:
        status = "modified"

    return DiffFile(
        path=path,
        old_path=old_path,
        new_path=new_path,
        status=status,
        binary=binary,
        hunks=hunks,
        property_changes=property_changes,
        raw_fallback=fallback,
    )


def _text(node: ET.Element | None) -> str:
    return node.text if node is not None and node.text is not None else ""
