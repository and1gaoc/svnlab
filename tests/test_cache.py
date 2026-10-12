import pytest

from svnlab.cache import SourceCache


@pytest.mark.asyncio
async def test_source_cache_reuses_loader_and_preserves_trailing_line() -> None:
    cache = SourceCache(ttl_seconds=60, max_entries=2, max_bytes=1024)
    calls = 0

    async def load() -> str:
        nonlocal calls
        calls += 1
        return "one\ntwo\n"

    first = await cache.get_or_load("key", load)
    second = await cache.get_or_load("key", load)
    assert first == ["one", "two", ""]
    assert second is first
    assert calls == 1


@pytest.mark.asyncio
async def test_source_cache_evicts_oldest_entry() -> None:
    cache = SourceCache(ttl_seconds=60, max_entries=1, max_bytes=1024)
    calls = {"a": 0}

    async def load_a() -> str:
        calls["a"] += 1
        return "a"

    async def load_b() -> str:
        return "b"

    await cache.get_or_load("a", load_a)
    await cache.get_or_load("b", load_b)
    await cache.get_or_load("a", load_a)
    assert calls["a"] == 2

