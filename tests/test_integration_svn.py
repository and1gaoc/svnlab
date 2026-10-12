from __future__ import annotations

import asyncio
import shutil
import subprocess

import pytest

from svnlab.models import RepositoryConnection
from svnlab.svn_client import SvnClient

pytestmark = pytest.mark.skipif(
    not shutil.which("svn") or not shutil.which("svnadmin"),
    reason="svn and svnadmin are required for the local repository integration test",
)


async def run_command(*args: str) -> None:
    await asyncio.to_thread(subprocess.run, list(args), check=True, capture_output=True)


@pytest.mark.asyncio
async def test_real_local_repository_log_diff_and_content(tmp_path) -> None:
    repository = tmp_path / "repository"
    working = tmp_path / "working"
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "alpha.txt").write_text("one\ntwo\n", encoding="utf-8")
    await run_command("svnadmin", "create", str(repository))
    url = repository.as_uri()
    await run_command("svn", "import", str(seed), url, "-m", "initial")
    await run_command("svn", "checkout", url, str(working))
    (working / "alpha.txt").write_text("one\nchanged\n", encoding="utf-8")
    (working / "beta.txt").write_text("new\n", encoding="utf-8")
    await run_command("svn", "add", str(working / "beta.txt"))
    await run_command("svn", "commit", str(working), "-m", "change two files")

    client = SvnClient()
    connection = RepositoryConnection(repository=url)
    commits = await client.commits(connection, limit=10)
    commit, diffs = await client.revision(connection, commits[0].revision)
    content = await client.file_text(connection, "alpha.txt", commit.revision)
    assert commit.message == "change two files"
    assert {item.path for item in diffs} == {"alpha.txt", "beta.txt"}
    assert "changed" in content

