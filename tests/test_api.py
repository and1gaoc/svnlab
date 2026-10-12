from fastapi.testclient import TestClient

from svnlab.app import create_app
from svnlab.cache import RepositoryCache
from svnlab.models import ChangedPath, Commit, DiffFile, DiffHunk, DiffLine

CONNECTION = {"repository": "https://svn.example/repo", "username": "ada", "password": "secret"}


class FakeSvnClient:
    class Settings:
        svn_executable = "svn"

    settings = Settings()

    def __init__(self) -> None:
        self.commit_calls = 0
        self.revision_calls = 0
        self.file_calls = 0

    async def info(self, connection):
        return {"revision": 7, "kind": "dir", "url": connection.repository, "repository_root": connection.repository, "repository_uuid": "abc"}

    async def commits(self, connection, *, limit, before_revision=None):
        self.commit_calls += 1
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
        self.revision_calls += 1
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
        self.file_calls += 1
        return "one\ntwo\nthree\n"


def client(tmp_path, svn_client=None) -> TestClient:
    return TestClient(
        create_app(
            svn_client=svn_client or FakeSvnClient(),
            repository_cache=RepositoryCache(tmp_path / "cache.sqlite3"),
        )
    )


def test_health_and_static_index(tmp_path) -> None:
    with client(tmp_path) as browser:
        assert browser.get("/api/health").json()["status"] == "ok"
        assert "SVNLab" in browser.get("/").text


def test_repository_commits_revision_and_content_contracts(tmp_path) -> None:
    fake = FakeSvnClient()
    with client(tmp_path, fake) as browser:
        checked = browser.post("/api/repository/check", json={"connection": CONNECTION})
        assert checked.status_code == 200
        commits = browser.post("/api/commits", json={"connection": CONNECTION, "limit": 30})
        assert commits.json()["commits"][0]["changed_file_count"] == 1
        assert commits.json()["cache_hit"] is False
        cached_commits = browser.post("/api/commits", json={"connection": CONNECTION, "limit": 30})
        assert cached_commits.json()["cache_hit"] is True
        assert fake.commit_calls == 1
        refreshed = browser.post(
            "/api/commits",
            json={"connection": CONNECTION, "limit": 30, "refresh": True},
        )
        assert refreshed.json()["cache_hit"] is False
        assert fake.commit_calls == 2
        detail = browser.post("/api/commits/7", json={"connection": CONNECTION})
        assert detail.json()["diffs"][0]["hunks"][0]["lines"][0]["content"] == "new"
        assert browser.post("/api/commits/7", json={"connection": CONNECTION}).json()["cache_hit"] is True
        assert fake.revision_calls == 1
        content = browser.post(
            "/api/files/content",
            json={"connection": CONNECTION, "path": "src/app.py", "revision": 7, "start_line": 2, "line_count": 2},
        )
        assert content.json()["lines"] == ["two", "three"]
        earlier = browser.post(
            "/api/files/content",
            json={"connection": CONNECTION, "path": "src/app.py", "revision": 7, "start_line": 1, "line_count": 1},
        )
        assert earlier.json()["lines"] == ["one"]
        assert earlier.json()["cache_hit"] is True
        assert fake.file_calls == 1
        assert content.headers["cache-control"] == "no-store"
    assert b"secret" not in (tmp_path / "cache.sqlite3").read_bytes()


def test_validation_rejects_credentials_in_query_shaped_bad_body(tmp_path) -> None:
    with client(tmp_path) as browser:
        response = browser.post("/api/commits", json={"connection": {"repository": "ftp://bad"}})
        assert response.status_code == 422
        response = browser.post("/api/commits/0", json={"connection": CONNECTION})
        assert response.status_code == 422

