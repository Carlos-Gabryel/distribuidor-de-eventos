import io
import urllib.error

from distrib.sprites import PNG, SpriteCache

IMAGE = PNG + b"\x00" * 50


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_downloads_once_and_caches(tmp_path):
    calls = []

    def opener(url, timeout):
        calls.append(url)
        return Resp(IMAGE)

    cache = SpriteCache(tmp_path, opener=opener)
    assert cache.cached(25) is None
    path = cache.get(25)
    assert path == tmp_path / "25.png" and path.read_bytes() == IMAGE
    assert cache.get(25) == path
    assert calls == ["https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png"]


def test_404_is_remembered(tmp_path):
    calls = []

    def opener(url, timeout):
        calls.append(url)
        raise urllib.error.HTTPError(url, 404, "nf", None, None)

    cache = SpriteCache(tmp_path, opener=opener)
    assert cache.get(9999) is None and cache.get(9999) is None
    assert len(calls) == 1


def test_offline_returns_none_and_cools_down(tmp_path):
    now = [0.0]
    calls = []

    def opener(url, timeout):
        calls.append(url)
        raise urllib.error.URLError("offline")

    cache = SpriteCache(tmp_path, opener=opener, clock=lambda: now[0])
    assert cache.get(1) is None and cache.get(2) is None
    assert len(calls) == 1
    now[0] = 61.0
    assert cache.get(2) is None and len(calls) == 2


def test_rejects_non_png_and_species_zero(tmp_path):
    cache = SpriteCache(tmp_path, opener=lambda url, timeout: Resp(b"<html>"))
    assert cache.get(5) is None
    assert cache.get(0) is None
