"""As telas (Textual). Só conversam com o catálogo, o distributor e as checagens."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from typing import Callable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, OptionList, Static
from textual.widgets.option_list import Option

from distrib.catalog import Catalog, Event, Favorites, load_index
from distrib.config import Config
from distrib.distributor import Status


@dataclass
class Services:
    cfg: Config | None
    adapters: dict
    catalogs: dict[str, Catalog]
    favorites: Favorites
    checks: Callable[[], list]
    make_distributor: Callable


def default_services(cfg: Config) -> Services:
    from distrib import radio
    from distrib.distributor import Distributor
    from distrib.games import ADAPTERS
    catalogs = {g: load_index(g, cfg.catalog_dir / g / "index.json") for g in ADAPTERS}

    def make_distributor(adapter, event):
        log = cfg.logs_dir / f"{date.today():%Y-%m-%d}.log"
        return Distributor(adapter.mode, adapter.parse_line,
                           lambda port: adapter.build_job(event, cfg, port), log,
                           radio.find_port, max_failures=3)

    return Services(cfg, ADAPTERS, catalogs, Favorites(cfg.state_dir / "favoritos.json"),
                    lambda: radio.run_checks(cfg, catalogs), make_distributor)


class CheckScreen(Screen):
    BINDINGS = [Binding("enter", "go", "Continuar"), Binding("r", "recheck", "Checar de novo"),
                Binding("q", "app.quit", "Sair")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Checando…", id="checks")
        yield Footer()

    def on_mount(self) -> None:
        self.action_recheck()

    def action_recheck(self) -> None:
        self.results = self.app.services.checks()
        lines = [f"{'✓' if c.ok else '✗'} {c.name}: {c.message}" for c in self.results]
        self.query_one("#checks", Static).update("\n".join(lines))

    def action_go(self) -> None:
        if all(c.ok for c in self.results if c.name in ("Placa", "prod.keys")):
            self.app.push_screen(GameScreen())
        else:
            self.notify("Resolva a placa e o prod.keys antes de continuar.", severity="error")


class GameScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Voltar"), Binding("q", "app.quit", "Sair")]

    def compose(self) -> ComposeResult:
        yield Header()
        options = []
        for game, adapter in self.app.services.adapters.items():
            n = len(self.app.services.catalogs.get(game, Catalog(game)).events)
            options.append(Option(f"{adapter.title}  ({n} eventos)", id=game))
        yield OptionList(*options, id="jogos")
        yield Footer()

    def on_option_list_option_selected(self, message: OptionList.OptionSelected) -> None:
        game = message.option.id
        self.app.push_screen(CatalogScreen(self.app.services.adapters[game]))


class CatalogScreen(Screen):
    BINDINGS = [Binding("f", "favorite", "Vitrine"), Binding("i", "items", "Itens/BP"),
                Binding("escape", "app.pop_screen", "Voltar")]

    def __init__(self, adapter):
        super().__init__()
        self.adapter = adapter
        self.catalog: Catalog = None
        self.include_items = False
        self._shown: list[Event] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder="Buscar (nome, espécie, OT)…", id="busca")
        with Horizontal():
            yield OptionList(id="lista")
            yield Static("", id="detalhes")
        yield Footer()

    def on_mount(self) -> None:
        self.catalog = self.app.services.catalogs[self.adapter.game]
        self.title = self.adapter.title
        self.refresh_list()

    def favorite_keys(self) -> list[str]:
        fav = self.app.services.favorites
        return [e.key for e in self._shown if fav.contains(e)]

    def visible_keys(self) -> list[str]:
        return [e.key for e in self._shown]

    def refresh_list(self) -> None:
        text = self.query_one("#busca", Input).value
        found = self.catalog.search(text, include_items=self.include_items)
        fav = self.app.services.favorites
        self._shown = [e for e in found if fav.contains(e)] + \
                      [e for e in found if not fav.contains(e)]
        lista = self.query_one("#lista", OptionList)
        highlighted = lista.highlighted
        lista.clear_options()
        lista.add_options([Option(("★ " if fav.contains(e) else "  ") + e.name, id=e.key)
                           for e in self._shown])
        if self._shown:
            lista.highlighted = min(highlighted or 0, len(self._shown) - 1)
        self.show_details()

    def current(self) -> Event | None:
        lista = self.query_one("#lista", OptionList)
        if lista.highlighted is None or not self._shown:
            return None
        return self._shown[lista.highlighted]

    def show_details(self) -> None:
        event = self.current()
        text = "" if event is None else event.name + "\n\n" + "\n".join(
            f"{label}: {value}" for label, value in event.details)
        self.query_one("#detalhes", Static).update(text)

    def on_input_changed(self, message: Input.Changed) -> None:
        self.refresh_list()

    def on_input_submitted(self, message: Input.Submitted) -> None:
        self.query_one("#lista", OptionList).focus()     # Enter na busca vai para a lista

    def on_option_list_option_highlighted(self, message: OptionList.OptionHighlighted) -> None:
        self.show_details()

    def on_option_list_option_selected(self, message: OptionList.OptionSelected) -> None:
        event = self.catalog.get(message.option.id)
        self.app.distribute(self.adapter, event)

    def action_favorite(self) -> None:
        event = self.current()
        if event is not None:
            self.app.services.favorites.toggle(event)
            self.refresh_list()

    def action_items(self) -> None:
        self.include_items = not self.include_items
        self.refresh_list()


def format_status(status: Status, mode: str, now: float) -> str:
    if status.state == "no_board":
        return "⚠ placa desconectada: replugue a placa; volto sozinho quando ela aparecer"
    if status.state == "failed":
        return ("✗ PAROU depois de 3 falhas seguidas\n"
                f"Último erro: {status.detail or '(veja o log em logs/)'}\n"
                "Aperte T para escolher de novo ou Q para sair.")
    if status.state == "paused":
        return "⏸ PAUSADO: aperte P para voltar"
    if status.state == "starting":
        head = "… subindo o host"
    elif mode == "session":
        head = "● CONSOLE CONECTADO" if status.state == "console" else "● AGUARDANDO CONSOLE"
    else:
        elapsed = int(now - status.since) if status.since is not None else 0
        head = f"● NO AR há {elapsed // 60:02d}:{elapsed % 60:02d}"
    lines = [head, status.label]
    if mode == "session":
        lines.append(f"Entregas: {status.deliveries}")
        if status.detail:
            lines.append(f"Última: {status.detail}")
        if status.last_event:
            lines.append(f"Resultado da última sessão: {status.last_event}")
        if status.last_event == "equipe cheia":
            lines.append("→ peça para o jogador liberar um espaço na equipe e tentar de novo")
    else:
        lines.append(f"Canal {status.channel or '?'} · reinícios: {status.restarts}")
    return "\n".join(lines)


class OnAirScreen(Screen):
    BINDINGS = [Binding("t", "switch", "Trocar evento"), Binding("p", "pause", "Pausar"),
                Binding("q", "quit_all", "Sair")]

    def __init__(self, adapter, event: Event, distributor):
        super().__init__()
        self.adapter, self.event, self.distributor = adapter, event, distributor

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("", id="estado")
            yield Static(self.adapter.instructions, id="instrucoes")
        yield Footer()

    def on_mount(self) -> None:
        self.tick()
        self.set_interval(0.5, self.tick)

    def tick(self) -> None:
        text = format_status(self.distributor.status(), self.adapter.mode, time.monotonic())
        self.query_one("#estado", Static).update(text)

    def action_switch(self) -> None:
        self.app.pop_screen()

    def action_pause(self) -> None:
        if self.distributor.status().state == "paused":
            self.distributor.resume()
        else:
            self.distributor.pause()
        self.tick()

    def action_quit_all(self) -> None:
        self.app.stop_distribution()
        self.app.exit()


class DistribApp(App):
    TITLE = "Distribuidor de Eventos — pokeldn"
    CSS = """
    #lista { width: 1fr; }
    #detalhes { width: 1fr; padding: 1 2; border: round $accent; }
    #checks { padding: 1 2; }
    """

    def __init__(self, services: Services):
        super().__init__()
        self.services = services
        self.last_pick: tuple[str, str] | None = None
        self.distributor = None

    def on_mount(self) -> None:
        self.push_screen(CheckScreen())

    def distribute(self, adapter, event: Event) -> None:
        self.last_pick = (adapter.game, event.key)
        self.stop_distribution()
        self.distributor = self.services.make_distributor(adapter, event)
        self.distributor.start()
        if isinstance(self.screen, OnAirScreen):
            self.pop_screen()
        self.push_screen(OnAirScreen(adapter, event, self.distributor))

    def stop_distribution(self) -> None:
        if self.distributor is not None:
            self.distributor.stop()
            self.distributor = None

    def on_unmount(self) -> None:
        self.stop_distribution()
