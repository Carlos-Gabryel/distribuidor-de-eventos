import json

from distrib.catalog import (INDEX_VERSION, Catalog, Event, Favorites, load_index, normalize,
                             save_index)


def ev(key, name, kind="pokemon", sort_key=None):
    return Event(game="swsh", key=key, name=name, kind=kind,
                 details=(("Espécie", "#893"),), files=(f"{key}.wc8",),
                 sort_key=sort_key or key)


def sample():
    return Catalog("swsh", [ev("b", "Jungle Zarude"), ev("a", "Pokémon Quest Tee", "item"),
                            ev("c", "Shiny Celebi")])


def test_normalize():
    assert normalize("Pokémon ÉÇÃ") == "pokemon eca"


def test_search_ignores_case_and_accents():
    cat = sample()
    assert [e.key for e in cat.search("ZARUDE")] == ["b"]
    assert [e.key for e in cat.search("pokemon", include_items=True)] == ["a"]


def test_search_hides_items_by_default_and_sorts():
    cat = sample()
    assert [e.key for e in cat.search("")] == ["b", "c"]
    assert [e.key for e in cat.search("", include_items=True)] == ["a", "b", "c"]


def test_get():
    assert sample().get("c").name == "Shiny Celebi"


def test_index_roundtrip(tmp_path):
    cat = sample()
    cat.invalid = 2
    path = tmp_path / "swsh" / "index.json"
    save_index(cat, path)
    back = load_index("swsh", path)
    assert back.events == cat.events
    assert back.invalid == 2


def test_load_index_missing_or_bad_returns_empty(tmp_path):
    assert load_index("swsh", tmp_path / "nao-existe.json").events == []
    bad = tmp_path / "bad.json"
    bad.write_text("{isto nao e json", encoding="utf-8")
    assert load_index("swsh", bad).events == []
    old = tmp_path / "old.json"
    old.write_text(json.dumps({"version": INDEX_VERSION + 99, "events": []}), encoding="utf-8")
    assert load_index("swsh", old).events == []


def test_favorites_toggle_and_persist(tmp_path):
    path = tmp_path / "state" / "favoritos.json"
    fav = Favorites(path)
    e = ev("b", "Jungle Zarude")
    assert fav.toggle(e) is True
    assert Favorites(path).contains(e)
    assert fav.toggle(e) is False
    assert not Favorites(path).contains(e)
