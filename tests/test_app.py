import asyncio

from distrib.app import CatalogScreen, CheckScreen, DistribApp, GameScreen, Services
from distrib.catalog import Catalog, Event, Favorites
from distrib.games.frlg import FrlgAdapter
from distrib.games.swsh import SwshAdapter
from distrib.radio import Check


def ev(game, key, name, kind="pokemon"):
    return Event(game, key, name, kind, (("Espécie", "#893"), ("Nível", "60")), (f"{key}.x",), key)


def services(tmp_path, checks_ok=True, distributor=None):
    catalogs = {
        "swsh": Catalog("swsh", [ev("swsh", "a", "Jungle Zarude"),
                                 ev("swsh", "b", "Item Poke Ball x100", "item"),
                                 ev("swsh", "c", "Shiny Celebi")]),
        "frlg": Catalog("frlg", [ev("frlg", "x", "10ANNIV Lugia (ENG)")]),
    }
    return Services(
        cfg=None, adapters={"swsh": SwshAdapter(), "frlg": FrlgAdapter(None)},
        catalogs=catalogs, favorites=Favorites(tmp_path / "fav.json"),
        checks=lambda: [Check("Placa", checks_ok, "ok" if checks_ok else "Plugue a placa")],
        make_distributor=lambda adapter, event: distributor)


def run(coro):
    return asyncio.run(coro)


def test_check_screen_blocks_until_ok(tmp_path):
    async def go():
        app = DistribApp(services(tmp_path, checks_ok=False))
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, CheckScreen)
            await pilot.press("enter")
            assert isinstance(app.screen, CheckScreen)
    run(go())


def test_flow_to_catalog_and_search(tmp_path):
    async def go():
        app = DistribApp(services(tmp_path))
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")                  # checagem ok -> jogos
            assert isinstance(app.screen, GameScreen)
            await pilot.press("enter")                  # Sword/Shield
            assert isinstance(app.screen, CatalogScreen)
            assert app.screen.visible_keys() == ["a", "c"]
            await pilot.press(*"celebi")
            await pilot.pause()
            assert app.screen.visible_keys() == ["c"]
            await pilot.press("enter")                  # Enter na busca foca a lista
            assert app.screen.focused.id == "lista"
    run(go())


def test_items_toggle_and_favorites_first(tmp_path):
    async def go():
        s = services(tmp_path)
        app = DistribApp(s)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter", "enter")
            screen = app.screen
            screen.query_one("#lista").focus()
            await pilot.press("i")
            assert screen.visible_keys() == ["a", "b", "c"]
            await pilot.press("down")                   # segundo item
            await pilot.press("f")
            await pilot.pause()
            assert screen.visible_keys()[0] == screen.favorite_keys()[0]
            assert len(screen.favorite_keys()) == 1
    run(go())


def test_enter_on_event_calls_distribute(tmp_path):
    async def go():
        app = DistribApp(services(tmp_path))
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter", "down", "enter")   # FireRed/LeafGreen
            screen = app.screen
            screen.query_one("#lista").focus()
            await pilot.press("enter")
            await pilot.pause()
            assert app.last_pick == ("frlg", "x")
    run(go())
