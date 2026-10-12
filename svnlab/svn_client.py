from __future__ import annotations

import asyncio
import locale
import os
from pathlib import PurePosixPath

from .config import DEFAULT_SETTINGS, Settings
from .errors import (
    SvnAuthenticationError,
    SvnBinaryFileError,
    SvnCertificateError,
    SvnConnectionError,
    SvnDecodeError,
    SvnNotFoundError,
    SvnNotInstalledError,
    SvnTimeoutError,
)
from .models import Commit, DiffFile, RepositoryConnection
from .parsers import parse_info_xml, parse_log_xml, parse_svn_diff


class SvnClient:
    def __init__(self, settings: Settings = DEFAULT_SETTINGS) -> None:
        self.settings = settings
        self._semaphore = asyncio.Semaphore(settings.max_svn_processes)

    async def info(self, connection: RepositoryConnection) -> dict[str, str | int | None]:
        output = await self._run(
            connection,
            ["info", "--xml", self._peg(connection.repository)],
            timeout=self.settings.info_timeout_seconds,
        )
        return parse_info_xml(output)

    async def commits(
        self,
        connection: RepositoryConnection,
        *,
        limit: int,
        before_revision: int | None = None,
    ) -> list[Commit]:
        args = ["log", "--xml", "--verbose", "--limit", str(limit)]
        if before_revision is not None:
            args.extend(["-r", f"{before_revision}:1"])
        args.append(self._peg(connection.repository))
        output = await self._run(
            connection, args, timeout=self.settings.log_timeout_seconds
        )
        return parse_log_xml(output)

    async def revision(
        self, connection: RepositoryConnection, revision: int
    ) -> tuple[Commit, list[DiffFile]]:
        log_args = [
            "log",
            "--xml",
            "--verbose",
            "-r",
            str(revision),
            self._peg(connection.repository),
        ]
        diff_args = [
            "diff",
            "-c",
            str(revision),
            self._peg(connection.repository),
        ]
        log_output, diff_output = await asyncio.gather(
            self._run(connection, log_args, timeout=self.settings.log_timeout_seconds),
            self._run(connection, diff_args, timeout=self.settings.diff_timeout_seconds),
        )
        commits = parse_log_xml(log_output)
        if not commits:
            raise SvnNotFoundError(f"Revision r{revision} was not found.")
        return commits[0], parse_svn_diff(diff_output)

    async def file_text(
        self, connection: RepositoryConnection, path: str, revision: int
    ) -> str:
        target = self._join_target(connection.repository, path)
        payload = await self._run_bytes(
            connection,
            ["cat", "-r", str(revision), self._peg(target, revision)],
            timeout=self.settings.content_timeout_seconds,
        )
        if b"\x00" in payload[:8192]:
            raise SvnBinaryFileError("This file is binary and cannot be shown as text.")
        for encoding in ("utf-8-sig", locale.getpreferredencoding(False)):
            try:
                return payload.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                continue
        raise SvnDecodeError("The file content could not be decoded as text.")

    async def _run(
        self,
        connection: RepositoryConnection,
        args: list[str],
        *,
        timeout: float,
    ) -> str:
        payload = await self._run_bytes(connection, args, timeout=timeout)
        try:
            return payload.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise SvnDecodeError("SVN returned text in an unsupported encoding.") from exc

    async def _run_bytes(
        self,
        connection: RepositoryConnection,
        args: list[str],
        *,
        timeout: float,
    ) -> bytes:
        command = [self.settings.svn_executable, *args, *self._auth_args(connection)]
        env = os.environ.copy()
        env.setdefault("LC_ALL", "C.UTF-8")
        env.setdefault("LANG", "C.UTF-8")

        async with self._semaphore:
            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
            except FileNotFoundError as exc:
                raise SvnNotInstalledError("The svn command-line client was not found.") from exc

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            except TimeoutError as exc:
                process.kill()
                await process.communicate()
                raise SvnTimeoutError("The SVN command timed out.") from exc

        if process.returncode != 0:
            self._raise_process_error(stderr, connection)
        return stdout

    @staticmethod
    def _auth_args(connection: RepositoryConnection) -> list[str]:
        args = ["--non-interactive", "--no-auth-cache"]
        if connection.username:
            args.extend(["--username", connection.username])
        if connection.password:
            args.extend(["--password", connection.password])
        return args

    @staticmethod
    def _peg(target: str, revision: int | None = None) -> str:
        if revision is not None:
            return f"{target}@{revision}"
        return f"{target}@" if "@" in target else target

    @staticmethod
    def _join_target(repository: str, path: str) -> str:
        clean = str(PurePosixPath("/" + path.replace("\\", "/"))).lstrip("/")
        return f"{repository.rstrip('/')}/{clean}" if clean not in {"", "."} else repository

    @staticmethod
    def _raise_process_error(stderr: bytes, connection: RepositoryConnection) -> None:
        decoded = stderr.decode("utf-8", errors="replace").strip()
        safe = decoded.replace(connection.password, "***") if connection.password else decoded
        lowered = safe.lower()
        if any(token in lowered for token in ("authentication failed", "authorization failed", "e170001", "e215004")):
            raise SvnAuthenticationError("SVN authentication failed.")
        if any(token in lowered for token in ("certificate", "server ssl certificate", "e230001")):
            raise SvnCertificateError("The SVN server certificate is not trusted.")
        if any(token in lowered for token in ("path not found", "non-existent", "does not exist", "e160013")):
            raise SvnNotFoundError("The requested SVN path or revision was not found.")
        message = safe.splitlines()[-1] if safe else "The SVN command failed."
        raise SvnConnectionError(message[:800])

