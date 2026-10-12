import pytest

from svnlab.config import Settings
from svnlab.encoding import decode_svn_text
from svnlab.errors import SvnAuthenticationError, SvnCertificateError, SvnNotFoundError
from svnlab.models import RepositoryConnection
from svnlab.svn_client import SvnClient


def test_remote_operation_timeouts_allow_slow_repositories() -> None:
    settings = Settings()
    assert settings.info_timeout_seconds == 60
    assert settings.log_timeout_seconds == 180
    assert settings.content_timeout_seconds == 300
    assert settings.diff_timeout_seconds == 600


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
    assert (
        SvnClient._join_target("https://example/repo", "/src/app.py")
        == "https://example/repo/src/app.py"
    )


def test_decode_svn_text_supports_utf_bom_and_gb18030() -> None:
    assert decode_svn_text("中文内容".encode("utf-16")) == "中文内容"
    assert decode_svn_text("修复编码问题".encode("gb18030")) == "修复编码问题"


@pytest.mark.asyncio
async def test_file_text_decodes_gb18030(monkeypatch) -> None:
    client = SvnClient()

    async def fake_run_bytes(*args, **kwargs):
        return "第一行\n第二行".encode("gb18030")

    monkeypatch.setattr(client, "_run_bytes", fake_run_bytes)
    connection = RepositoryConnection(repository="https://svn.example/repo")

    assert await client.file_text(connection, "说明.txt", 8) == "第一行\n第二行"


@pytest.mark.parametrize(
    ("message", "error_type"),
    [
        (b"svn: E170001: Authentication failed for 'secret'", SvnAuthenticationError),
        (
            b"svn: E230001: Server SSL certificate verification failed",
            SvnCertificateError,
        ),
        (b"svn: E160013: path not found", SvnNotFoundError),
    ],
)
def test_process_errors_are_classified_and_password_is_not_exposed(
    message, error_type
) -> None:
    connection = RepositoryConnection(
        repository="https://svn.example/repo", password="secret"
    )
    with pytest.raises(error_type) as caught:
        SvnClient._raise_process_error(message, connection)
    assert "secret" not in str(caught.value)
