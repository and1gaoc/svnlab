import sqlite3

import pytest

from svnlab.cache import RepositoryCache


@pytest.mark.asyncio
async def test_repository_cache_survives_new_instance(tmp_path) -> None:
    path = tmp_path / "cache.sqlite3"
    key = RepositoryCache.key("https://svn.example/repo", "ada", "file", 7, "a.py")
    calls = 0

    async def load() -> str:
        nonlocal calls
        calls += 1
        return "one\ntwo\n"

    first, first_hit = await RepositoryCache(path).get_or_load_text(key, load)
    second, second_hit = await RepositoryCache(path).get_or_load_text(key, load)

    assert first == second == "one\ntwo\n"
    assert first_hit is False
    assert second_hit is True
    assert calls == 1


@pytest.mark.asyncio
async def test_cache_scope_isolated_by_repository_and_username(tmp_path) -> None:
    cache = RepositoryCache(tmp_path / "cache.sqlite3")
    ada_key = cache.key("https://svn.example/repo", "ada", "revision", 9)
    lin_key = cache.key("https://svn.example/repo", "lin", "revision", 9)
    other_key = cache.key("https://svn.example/other", "ada", "revision", 9)

    assert len({ada_key, lin_key, other_key}) == 3
    assert "ada" not in ada_key
    assert "svn.example" not in ada_key


@pytest.mark.asyncio
async def test_refresh_failure_preserves_previous_value(tmp_path) -> None:
    cache = RepositoryCache(tmp_path / "cache.sqlite3")
    key = cache.key("https://svn.example/repo", "ada", "commits", 30, None)

    async def original() -> str:
        return "cached"

    async def failing_refresh() -> str:
        raise RuntimeError("network interrupted")

    await cache.get_or_load_text(key, original)
    with pytest.raises(RuntimeError, match="network interrupted"):
        await cache.get_or_load_text(key, failing_refresh, refresh=True)

    value, cache_hit = await RepositoryCache(cache.path).get_or_load_text(
        key, failing_refresh
    )
    assert value == "cached"
    assert cache_hit is True


@pytest.mark.asyncio
async def test_invalid_json_entry_is_reloaded(tmp_path) -> None:
    path = tmp_path / "cache.sqlite3"
    cache = RepositoryCache(path)
    key = cache.key("https://svn.example/repo", "ada", "commits", 30, None)

    async def initial() -> dict[str, object]:
        return {"commits": []}

    await cache.get_or_load_json(key, initial)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE cache_entries SET payload = ? WHERE cache_key = ?", ("{", key)
        )

    calls = 0

    async def replacement() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"commits": [{"revision": 8}]}

    value, cache_hit = await RepositoryCache(path).get_or_load_json(key, replacement)
    assert value == {"commits": [{"revision": 8}]}
    assert cache_hit is False
    assert calls == 1
