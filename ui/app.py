"""A janela: barra lateral (abas + cartão da placa), faixa de atualização e a view da aba atual."""
from __future__ import annotations

import sys
import threading
import time
import traceback
from pathlib import Path

import flet as ft

from distrib import update
from distrib.config import load, resource_root
from distrib.service import Service, Snapshot
from ui import theme as t

ASSETS = resource_root() / "ui" / "assets"
NAV = (("distribuir", "Distribuir", "gamepad-2"), ("placa", "Placa", "cpu"),
       ("ajustes", "Ajustes", "settings"))


class Shell:
    def __init__(self, page: ft.Page, service: Service):
        from ui.views.placeholder import Placeholder
        self.page, self.service = page, service
        self.picker = ft.FilePicker()
        self.launcher = ft.UrlLauncher()
        from ui.views.distribuir import DistribuirView
        self.views = {key: Placeholder(self, label) for key, label, _ in NAV}
        self.views["distribuir"] = DistribuirView(self)
        self.inicio = Placeholder(self, "Primeira abertura")
        self.current = "distribuir"
        self._shown = None
        self._pending = False
        self._pending_lock = threading.Lock()
        self.nav = ft.Column(spacing=4)
        self.board_card = ft.Container()
        self.update_bar = ft.Container(visible=False, bgcolor=t.CARD, padding=ft.Padding(24, 10, 24, 10),
                                       border=ft.Border(bottom=ft.BorderSide(1, t.BORDER)))
        self.body = ft.Container(expand=True, padding=24)
        sidebar = ft.Container(
            width=t.SIDEBAR_WIDTH, bgcolor=t.SIDEBAR, padding=ft.Padding(12, 16, 12, 16),
            border=ft.Border(right=ft.BorderSide(1, t.BORDER)),
            content=ft.Column([t.brand(), ft.Container(height=12), self.nav,
                               ft.Container(expand=True), self.board_card], spacing=0, expand=True))
        page.add(ft.Row([sidebar, ft.Column([self.update_bar, self.body], spacing=0, expand=True)],
                        spacing=0, expand=True))
        service.subscribe(self._on_snapshot)
        self.in_thread(self._ticker)

    # ---- infraestrutura ----
    def ui(self, fn) -> None:
        """Roda fn no laço da página: controles não podem ser mexidos de outra thread."""
        async def call():
            try:
                fn()
            except Exception:
                traceback.print_exc()
        self.page.run_task(call)

    def in_thread(self, fn, *args) -> None:
        threading.Thread(target=fn, args=args, daemon=True).start()

    def toast(self, message: str) -> None:
        self.ui(lambda: self.page.show_dialog(ft.SnackBar(ft.Text(message), duration=4000)))

    def _ticker(self) -> None:
        # O tempo "no ar" anda sem mudar o Snapshot: redesenha uma vez por segundo durante a distribuição.
        while True:
            time.sleep(1)
            if self.service.snapshot().run is not None:
                self._on_snapshot(self.service.snapshot())

    def _on_snapshot(self, snap: Snapshot) -> None:      # de qualquer thread
        with self._pending_lock:
            if self._pending:
                return
            self._pending = True
        self.ui(self._flush)

    def _flush(self) -> None:
        with self._pending_lock:
            self._pending = False
        self.render()

    # ---- navegação e desenho ----
    def navigate(self, key: str) -> None:
        self.current = key
        self.render()

    def _active_view(self, snap: Snapshot):
        if self.current == "distribuir" and not snap.ready and snap.run is None:
            return self.inicio
        return self.views[self.current]

    def render(self) -> None:
        snap = self.service.snapshot()
        self.nav.controls = [t.nav_item(label, icon, key == self.current,
                                        lambda e, k=key: self.navigate(k)) for key, label, icon in NAV]
        self.board_card.content = t.board_card(snap.board)
        self.update_bar.visible = snap.update_state in ("ready", "error")
        if self.update_bar.visible:
            self.update_bar.content = self._update_row(snap)
        view = self._active_view(snap)
        if view is not self._shown:
            self._shown = view
            self.body.content = view.control
            view.show(snap)
        else:
            view.update(snap)
        self.page.update()

    def _update_row(self, snap: Snapshot) -> ft.Row:
        if snap.update_state == "error":
            return ft.Row([t.icon("triangle-alert", 16, t.AMBER),
                           t.muted("A atualização falhou. Baixe a versão nova no GitHub e substitua o .exe.")])
        busy = snap.run is not None
        return ft.Row([t.icon("download", 16, t.GREEN),
                       t.text(f"Atualização {snap.update_version} pronta.", 13),
                       t.muted("Reinicie quando a distribuição terminar." if busy else ""),
                       ft.Container(expand=True),
                       t.button("Reiniciar", self._restart, disabled=busy)], spacing=10)

    def _restart(self, e=None) -> None:
        if self.service.apply_update():
            self.page.run_task(self.page.window.destroy)


def _log_crashes(cfg) -> None:
    crash = cfg.logs_dir / "erros.log"

    def write(kind, value, tb):
        with open(crash, "a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            traceback.print_exception(kind, value, tb, file=f)

    sys.excepthook = write
    threading.excepthook = lambda args: write(args.exc_type, args.exc_value, args.exc_traceback)


def run() -> None:
    cfg = load()
    for folder in (cfg.data_dir, cfg.logs_dir):
        folder.mkdir(parents=True, exist_ok=True)
    exe = Path(sys.executable) if getattr(sys, "frozen", False) else None
    if exe is not None:
        update.cleanup(exe)
    _log_crashes(cfg)
    service = Service(cfg, exe_path=exe)

    def main(page: ft.Page) -> None:
        t.apply_page(page)
        Shell(page, service)
        service.start_background(updates=exe is not None)

    try:
        ft.run(main, assets_dir=str(ASSETS))
    finally:
        service.shutdown()
