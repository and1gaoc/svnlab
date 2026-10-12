import pytest
from pydantic import ValidationError

from svnlab.models import CommitListRequest, FileContentRequest, RepositoryConnection


def test_connection_accepts_supported_urls() -> None:
    for url in (
        "https://svn.example.com/repos/project",
        "svn://svn.example.com/project",
        "svn+ssh://svn.example.com/project",
        "file:///tmp/repository",
    ):
        assert RepositoryConnection(repository=url).repository == url


def test_connection_rejects_unsupported_or_control_characters() -> None:
    with pytest.raises(ValidationError):
        RepositoryConnection(repository="ftp://example.com/project")
    with pytest.raises(ValidationError):
        RepositoryConnection(repository="https://example.com/project\n--password")


def test_request_bounds_are_enforced() -> None:
    connection = RepositoryConnection(repository="https://svn.example.com/repo")
    with pytest.raises(ValidationError):
        CommitListRequest(connection=connection, limit=101)
    with pytest.raises(ValidationError):
        FileContentRequest(connection=connection, path="a.py", revision=2, start_line=0)
    with pytest.raises(ValidationError):
        FileContentRequest(connection=connection, path="a.py", revision=2, line_count=501)

