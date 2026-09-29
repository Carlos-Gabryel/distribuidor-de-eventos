import asyncio

from distrib.app import (CatalogScreen, CheckScreen, DistribApp, GameScreen, OnAirScreen,
                         Services, format_status)
from distrib.catalog import Catalog, Event, Favorites
from distrib.games.frlg import FrlgAdapter
from distrib.games.swsh import SwshAdapter
from distrib.distributor import Status
from distrib.radio import Check


class FakeDistributor:
    def __init__(self):
        self.calls = []
        self._status = Status(state="on_air", label="Jungle Zarude", since=0.0, channel=11)

    def start(self): self.calls.append("start")
    def stop(self): self.calls.append("stop")
    def pause(self): self.calls.append("pause"); self._status = Status(state="paused")
    def resume(self): self.calls.append("resume")
    def status(self): return self._status


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
        make_distributor=lambda adapter, event: distributor or FakeDistributor())


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


def test_format_status_broadcast():
    text = format_status(Status(state="on_air", label="Jungle Zarude", since=0.0, channel=11,
                                restarts=1), "broadcast", now=754.0)
    assert "● NO AR há 12:34" in text
    assert "Jungle Zarude" in text and "Canal 11" in text and "reinícios: 1" in text


def test_format_status_session_and_problems():
    text = format_status(Status(state="on_air", label="10ANNIV Lugia", since=0.0, deliveries=3,
                                last_event="equipe cheia", detail="LUGIA Nv70"), "session", 10.0)
    assert "AGUARDANDO CONSOLE" in text and "Entregas: 3" in text
    assert "equipe cheia" in text and "liberar um espaço" in text
    assert "placa desconectada" in format_status(Status(state="no_board"), "broadcast", 0.0)
    failed = format_status(Status(state="failed", detail="RuntimeError: x"), "broadcast", 0.0)
    assert "PAROU" in failed and "RuntimeError: x" in failed


def test_distribute_switch_pause_quit(tmp_path):
    first, second = FakeDistributor(), FakeDistributor()
    made = [first, second]

    async def go():
        s = services(tmp_path)
        s.make_distributor = lambda adapter, event: made.pop(0)
        app = DistribApp(s)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter", "enter")
            app.screen.query_one("#lista").focus()
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, OnAirScreen)
            assert first.calls == ["start"]
            await pilot.press("p")
            assert first.calls[-1] == "pause"
            await pilot.press("p")
            assert first.calls[-1] == "resume"
            await pilot.press("t")                      # volta ao catálogo, sem parar
            await pilot.pause()
            assert isinstance(app.screen, CatalogScreen) and "stop" not in first.calls
            app.screen.query_one("#lista").focus()
            await pilot.press("down", "enter")          # outro evento
            await pilot.pause()
            assert first.calls[-1] == "stop" and second.calls == ["start"]
            await pilot.press("q")
            await pilot.pause()
            assert second.calls[-1] == "stop"
    run(go())
