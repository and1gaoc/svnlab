from __future__ import annotations

import codecs
import locale


def decode_svn_text(payload: bytes) -> str:
    """Decode SVN text without assuming the repository file encoding is UTF-8."""
    if payload.startswith(codecs.BOM_UTF8):
        return payload.decode("utf-8-sig")
    if payload.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        return payload.decode("utf-32")
    if payload.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return payload.decode("utf-16")

    candidates = ["utf-8"]
    get_encoding = getattr(locale, "getencoding", None)
    if get_encoding is not None:
        candidates.append(get_encoding())
    candidates.extend([locale.getpreferredencoding(False), "gb18030"])

    tried: set[str] = set()
    for encoding in candidates:
        normalized = encoding.lower().replace("_", "-")
        if normalized in tried:
            continue
        tried.add(normalized)
        try:
            return payload.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue

    fallback = candidates[1] if len(candidates) > 1 else "utf-8"
    try:
        return payload.decode(fallback, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")
