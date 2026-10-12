from __future__ import annotations


class SvnLabError(Exception):
    code = "svn_error"
    status_code = 502
    default_hint: str | None = None

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint if hint is not None else self.default_hint


class SvnNotInstalledError(SvnLabError):
    code = "svn_not_installed"
    status_code = 503
    default_hint = "Install the Subversion command-line client and ensure svn is on PATH."


class SvnAuthenticationError(SvnLabError):
    code = "svn_authentication_failed"
    status_code = 401
    default_hint = "Check the SVN username and password."


class SvnCertificateError(SvnLabError):
    code = "svn_certificate_untrusted"
    status_code = 400
    default_hint = "Trust the server certificate with your SVN client, then try again."


class SvnNotFoundError(SvnLabError):
    code = "svn_not_found"
    status_code = 404


class SvnTimeoutError(SvnLabError):
    code = "svn_timeout"
    status_code = 504
    default_hint = "Check the repository connection or try a smaller request."


class SvnConnectionError(SvnLabError):
    code = "svn_connection_failed"
    status_code = 502
    default_hint = "Check the repository address and network connection."


class SvnBinaryFileError(SvnLabError):
    code = "binary_file"
    status_code = 422
    default_hint = "Binary files cannot be displayed as source text."


class SvnDecodeError(SvnLabError):
    code = "decode_failed"
    status_code = 422
    default_hint = "The file encoding is not supported by this SVNLab version."

