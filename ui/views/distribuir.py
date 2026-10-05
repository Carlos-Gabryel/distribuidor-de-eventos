"""Distribuir: Jogo → grade de Pokémon → eventos do Pokémon → distribuindo.

Parar volta para a grade do jogo; Pausar fica na tela. Trocar de aba não interrompe nada.
"""
from __future__ import annotations

import threading
import time

import flet as ft

from distrib.catalog import Event, Group
from ui import theme as t
from ui.sprites import SpriteSlots

GAMES = (("swsh", "Sword / Shield", "Vários consoles ao mesmo tempo", 888, ("#2B3A67", "#4B2B67")),
         ("frlg", "FireRed / LeafGreen", "Um console por vez", 6, ("#6B2B2B", "#6B4A2B")))
TITLES = {game: title for game, title, *_ in GAMES}
RUN_STATES = {"starting": "Preparando…", "on_air": "No ar", "console": "Console conectado",
              "paused": "Pausado", "no_board": "Esperando a placa", "failed": "Falhou",
              "idle": "Parado"}
RESULTS = {"entregue": "Entregue", "equipe cheia": "Equipe cheia", "não entregue": "Não entregue"}


def elapsed(since: float | None) -> str:
    if since is None:
        return "—"
    seconds = int(time.monotonic() - since)
    return f"{seconds // 3600:d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"


class DistribuirView:
    def __init__(self, shell):
        self.shell, self.service = shell, shell.service
        self.game: str | None = None
        self.group: Group | None = None
        self.stopping = False
        self._step: str | None = None
        self._timer: threading.Timer | None = None
        self.control = ft.Column(expand=True, spacing=t.GAP)
        self.search = ft.TextField(hint_text="Buscar Pokémon…", on_change=self._on_search,
                                   bgcolor=t.FIELD, border_color=t.BORDER, border_radius=t.RADIUS_SMALL,
                                   text_size=13, height=40, content_padding=ft.Padding(12, 8, 12, 8))
        self.grid = ft.GridView(max_extent=160, child_aspect_ratio=0.78, spacing=10,
                                run_spacing=10, expand=True)
        self.run_title = t.text("", 18, bold=True)
        self.run_state = t.muted("")
        self.pause_slot = ft.Container()
        self.stop_slot = ft.Container()
        self.stats = ft.Row(spacing=10)
        self.log = ft.ListView(expand=True, spacing=2, auto_scroll=True)

    # ---- ciclo da view ----
    def step(self, snap) -> str:
        if snap.run is not None:
            return "distribuindo"
        if self.group is not None:
            return "eventos"
        return "grade" if self.game is not None else "jogos"

    def show(self, snap) -> None:
        self._step = None
        self.update(snap)

    def update(self, snap) -> None:
        if snap.run is None:
            self.stopping = False
        step = self.step(snap)
        if step != self._step:
            self._step = step
            self.control.controls = getattr(self, f"_build_{step}")(snap)
        if step == "distribuindo":
            self._update_run(snap)

    def _redraw(self) -> None:
        self._step = None
        self.shell.render()

    # ---- 1. jogos ----
    def _build_jogos(self, snap) -> list[ft.Control]:
        slots = SpriteSlots(self.shell, 96)
        cards = []
        for game, title, subtitle, mascot, colors in GAMES:
            header = ft.Container(
                content=slots.box(mascot), height=150, border_radius=t.RADIUS_SMALL,
                alignment=ft.Alignment.CENTER,
                gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                           colors=list(colors)))
            body = ft.Column([header, t.text(title, 16, bold=True),
                              t.muted(f"{self.service.event_count(game)} eventos · {subtitle}")], spacing=8)
            if hidden := self.service.hidden_count(game):
                body.controls.append(t.muted(f"{hidden} eventos ocultos (recusados pelo PKHeX)"))
            cards.append(t.card(body, padding=16, expand=True,
                                on_click=lambda e, g=game: self._pick_game(g)))
        slots.load()
        return [t.crumbs([("Distribuir", None)]), ft.Row(cards, spacing=t.GAP)]

    def _pick_game(self, game: str) -> None:
        self.game, self.group = game, None
        self.search.value = ""
        self._redraw()

    def _to_games(self, e=None) -> None:
        self.game = self.group = None
        self._redraw()

    # ---- 2. grade ----
    def _build_grade(self, snap) -> list[ft.Control]:
        self._fill_grid()
        return [t.crumbs([("Distribuir", self._to_games), (TITLES[self.game], None)]),
                self.search, self.grid]

    def _fill_grid(self) -> None:
        slots = SpriteSlots(self.shell, 96)
        self.grid.controls = [self._tile(group, slots)
                              for group in self.service.groups(self.game, self.search.value or "")]
        slots.load()

    def _tile(self, group: Group, slots: SpriteSlots) -> ft.Container:
        n = len(group.events)
        center = ft.CrossAxisAlignment.CENTER
        body = ft.Column([
            slots.box(group.species) if group.species else ft.Container(
                t.icon("package" if group.key == "item" else "zap", 40, t.MUTED),
                width=96, height=96, alignment=ft.Alignment.CENTER),
            t.text(group.name, 13, bold=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            t.muted(f"{n} evento{'s' if n > 1 else ''}", 11),
            t.muted(" · ".join(group.highlights), 11, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
        ], horizontal_alignment=center, spacing=4)
        return t.card(body, padding=10, on_click=lambda e, g=group: self._pick_group(g))

    def _on_search(self, e) -> None:
        if self._timer is not None:
            self._timer.cancel()

        def refresh():
            self._fill_grid()
            self.grid.update()

        self._timer = threading.Timer(0.25, lambda: self.shell.ui(refresh))
        self._timer.start()

    def _pick_group(self, group: Group) -> None:
        self.group = group
        self._redraw()

    def _to_grid(self, e=None) -> None:
        self.group = None
        self._redraw()

    # ---- 3. eventos do Pokémon ----
    def _build_eventos(self, snap) -> list[ft.Control]:
        group = self.group
        slots = SpriteSlots(self.shell, 192)
        n = len(group.events)
        header = ft.Row([slots.box(group.species) if group.species else ft.Container(width=8),
                         ft.Column([t.text(group.name, 22, bold=True),
                                    t.muted(f"{n} evento{'s' if n > 1 else ''} disponíve{'is' if n > 1 else 'l'}")],
                                   spacing=4)], spacing=16)
        rows = [self._event_row(event, first=index == 0) for index, event in enumerate(group.events)]
        slots.load()
        return [t.crumbs([("Distribuir", self._to_games), (TITLES[self.game], self._to_grid),
                          (group.name, None)]),
                header, ft.ListView(rows, spacing=8, expand=True)]

    def _event_row(self, event: Event, first: bool) -> ft.Container:
        ot = dict(event.details).get("OT", "")
        line = " · ".join(p for p in (event.region, *event.highlights, f"OT {ot}" if ot else "") if p)
        return t.card(ft.Row([ft.Column([t.text(event.name, 13, bold=True), t.muted(line, 11)],
                                        spacing=2, expand=True),
                              t.button("Distribuir", lambda e, ev=event: self._start(ev), primary=first,
                                       icon_name="play")]), padding=12)

    def _start(self, event: Event) -> None:
        game = self.game

        def work():
            try:
                self.service.start(game, event)
            except RuntimeError as exc:
                self.shell.toast(f"Não deu para começar: {exc}")

        self.shell.in_thread(work)

    # ---- 4. distribuindo ----
    def _build_distribuindo(self, snap) -> list[ft.Control]:
        run = snap.run
        self.game = run.game
        slots = SpriteSlots(self.shell, 96)
        header = ft.Row([slots.box(run.event.species),
                         ft.Column([self.run_title, self.run_state], spacing=2, expand=True),
                         self.pause_slot, self.stop_slot], spacing=14)
        slots.load()
        name = self.group.name if self.group is not None else TITLES[run.game]
        return [t.crumbs([("Distribuir", None), (TITLES[run.game], None), (name, None),
                          (run.event.name, None)]),
                header, self.stats,
                t.muted(self.service.adapters[run.game].instructions, 12),
                t.card(self.log, padding=12, expand=True)]

    def _update_run(self, snap) -> None:
        run = snap.run
        self.run_title.value = run.event.name
        state = "Parando…" if self.stopping else RUN_STATES.get(run.state, run.state)
        if run.state == "failed" and run.detail:
            state += f" · {run.detail}"
        self.run_state.value = state
        paused = run.state == "paused"
        self.pause_slot.content = t.button("Continuar" if paused else "Pausar",
                                           self._resume if paused else self._pause, primary=False,
                                           icon_name="play" if paused else "pause",
                                           disabled=self.stopping)
        self.stop_slot.content = t.button("Parar", self._stop, icon_name="square", disabled=self.stopping)
        if self.service.adapters[run.game].mode == "broadcast":
            self.stats.controls = [t.stat("No ar há", elapsed(run.since)),
                                   t.stat("Canal", str(run.channel or "—"))]
        else:
            self.stats.controls = [t.stat("Entregues", str(run.deliveries)),
                                   t.stat("Último resultado", RESULTS.get(run.last_event, "—")),
                                   t.stat("No ar há", elapsed(run.since)),
                                   t.stat("Console", "conectado" if run.state == "console" else "—")]
        self.log.controls = [ft.Text(line, size=11, font_family="Consolas", color=t.MUTED, selectable=True)
                             for line in snap.log[-200:]]

    def _pause(self, e=None) -> None:
        self.shell.in_thread(self.service.pause)

    def _resume(self, e=None) -> None:
        self.shell.in_thread(self.service.resume)

    def _stop(self, e=None) -> None:
        run = self.service.snapshot().run
        if run is None:
            return
        self.stopping = True
        self.game, self.group = run.game, None        # ao parar, volta para a grade do jogo
        self.shell.in_thread(self.service.stop)
        self.shell.render()
