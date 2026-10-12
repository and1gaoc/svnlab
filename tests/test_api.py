from fastapi.testclient import TestClient

from svnlab.app import create_app
from svnlab.models import ChangedPath, Commit, DiffFile, DiffHunk, DiffLine

CONNECTION = {"repository": "https://svn.example/repo", "username": "ada", "password": "secret"}


class FakeSvnClient:
    class Settings:
        svn_executable = "svn"

    settings = Settings()

    async def info(self, connection):
        return {"revision": 7, "kind": "dir", "url": connection.repository, "repository_root": connection.repository, "repository_uuid": "abc"}

    async def commits(self, connection, *, limit, before_revision=None):
        return [
            Commit(
                revision=7,
                author="ada",
                date="2026-10-12T08:00:00Z",
                message="Update two files",
                changed_paths=[ChangedPath(path="/src/app.py", action="M")],
            )
        ]

    async def revision(self, connection, revision):
        commit = (await self.commits(connection, limit=1))[0]
        diff = DiffFile(
            path="src/app.py",
            hunks=[
                DiffHunk(
                    header="@@ -1 +1 @@",
                    old_start=1,
                    old_count=1,
                    new_start=1,
                    new_count=1,
                    lines=[DiffLine(kind="addition", content="new", new_line=1)],
                )
            ],
        )
        return commit, [diff]

    async def file_text(self, connection, path, revision):
        return "one\ntwo\nthree\n"


def client() -> TestClient:
    return TestClient(create_app(svn_client=FakeSvnClient()))


def test_health_and_static_index() -> None:
    with client() as browser:
        assert browser.get("/api/health").json()["status"] == "ok"
        assert "SVNLab" in browser.get("/").text


def test_repository_commits_revision_and_content_contracts() -> None:
    with client() as browser:
        checked = browser.post("/api/repository/check", json={"connection": CONNECTION})
        assert checked.status_code == 200
        commits = browser.post("/api/commits", json={"connection": CONNECTION, "limit": 30})
        assert commits.json()["commits"][0]["changed_file_count"] == 1
        detail = browser.post("/api/commits/7", json={"connection": CONNECTION})
        assert detail.json()["diffs"][0]["hunks"][0]["lines"][0]["content"] == "new"
        content = browser.post(
            "/api/files/content",
            json={"connection": CONNECTION, "path": "src/app.py", "revision": 7, "start_line": 2, "line_count": 2},
        )
        assert content.json()["lines"] == ["two", "three"]
        assert content.headers["cache-control"] == "no-store"


def test_validation_rejects_credentials_in_query_shaped_bad_body() -> None:
    with client() as browser:
        response = browser.post("/api/commits", json={"connection": {"repository": "ftp://bad"}})
        assert response.status_code == 422
        response = browser.post("/api/commits/0", json={"connection": CONNECTION})
        assert response.status_code == 422

