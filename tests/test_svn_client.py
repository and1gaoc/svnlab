import pytest

from svnlab.errors import SvnAuthenticationError, SvnCertificateError, SvnNotFoundError
from svnlab.models import RepositoryConnection
from svnlab.svn_client import SvnClient


def test_auth_arguments_disable_cache() -> None:
    connection = RepositoryConnection(
        repository="https://svn.example/repo", username="ada", password="secret"
    )
    assert SvnClient._auth_args(connection) == [
        "--non-interactive",
        "--no-auth-cache",
        "--username",
        "ada",
        "--password",
        "secret",
    ]


def test_peg_revision_and_target_joining_are_explicit() -> None:
    assert SvnClient._peg("https://example/repo@team") == "https://example/repo@team@"
    assert SvnClient._peg("https://example/repo", 8) == "https://example/repo@8"
    assert SvnClient._join_target("https://example/repo", "/src/app.py") == "https://example/repo/src/app.py"


@pytest.mark.parametrize(
    ("message", "error_type"),
    [
        (b"svn: E170001: Authentication failed for 'secret'", SvnAuthenticationError),
        (b"svn: E230001: Server SSL certificate verification failed", SvnCertificateError),
        (b"svn: E160013: path not found", SvnNotFoundError),
    ],
)
def test_process_errors_are_classified_and_password_is_not_exposed(message, error_type) -> None:
    connection = RepositoryConnection(repository="https://svn.example/repo", password="secret")
    with pytest.raises(error_type) as caught:
        SvnClient._raise_process_error(message, connection)
    assert "secret" not in str(caught.value)

