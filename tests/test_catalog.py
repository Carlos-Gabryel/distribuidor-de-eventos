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


from distrib.catalog import group_events, search_groups  # noqa: E402


def gev(key, species=0, kind="pokemon", name=None, highlights=(), region=""):
    return Event(game="swsh", key=key, name=name or key, kind=kind, details=(), files=(key,),
                 sort_key=key, species=species, highlights=highlights, region=region)


NAMES = {893: "Zarude", 25: "Pikachu"}.get


def test_group_events_by_species_items_last():
    groups = group_events([gev("b", 893, highlights=("Nv 60",)), gev("a", 25, highlights=("Shiny",)),
                           gev("c", 893, highlights=("Nv 70", "Nv 60")), gev("i", kind="item"),
                           gev("x", kind="extra")], lambda n: NAMES(n, f"#{n}"))
    assert [g.name for g in groups] == ["Pikachu", "Zarude", "Itens", "Presentes do pokeldn"]
    zarude = groups[1]
    assert zarude.key == "pokemon:893" and zarude.species == 893
    assert [e.key for e in zarude.events] == ["b", "c"]
    assert zarude.highlights == ("Nv 60", "Nv 70")


def test_search_groups_ignores_accents_and_case():
    groups = group_events([gev("Jungle Zarude", 893), gev("Pikachu Chapéu", 25)],
                          lambda n: NAMES(n, f"#{n}"))
    assert [g.name for g in search_groups(groups, "ZARUDE")] == ["Zarude"]
    assert [g.name for g in search_groups(groups, "chapeu")] == ["Pikachu"]
    assert search_groups(groups, "") == groups


def test_index_roundtrip_keeps_new_fields(tmp_path):
    cat = Catalog("swsh", [gev("z", 893, highlights=("Shiny",), region="Ocidente")])
    save_index(cat, tmp_path / "index.json")
    back = load_index("swsh", tmp_path / "index.json").events[0]
    assert (back.species, back.highlights, back.region) == (893, ("Shiny",), "Ocidente")
