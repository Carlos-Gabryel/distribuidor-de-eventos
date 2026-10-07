"""Ajustes: prod.keys, eventos, versão/atualização, logs e créditos."""
from __future__ import annotations

import os

import flet as ft

from distrib import __version__
from distrib.platform import IS_ANDROID
from ui import theme as t
from ui.views.inicio import choose_keys, download_events

CREDITS = (
    ("Distribuidor de Eventos, por Carlos Gabryel:", "https://github.com/Carlos-Gabryel/distribuidor-de-eventos"),
)
UPDATE_TEXT = {"none": "Você está na versão mais recente que encontramos.",
               "downloading": "Baixando a versão nova…", "ready": "Versão nova pronta: use “Reiniciar” no topo.",
               "error": "A última tentativa de atualizar falhou."}


class AjustesView:
    def __init__(self, shell):
        self.shell, self.service = shell, shell.service
        self.download_line = ""
        self.control = ft.Column(expand=True, spacing=t.GAP, scroll=ft.ScrollMode.AUTO)

    def show(self, snap) -> None:
        self.update(snap)

    def update(self, snap) -> None:
        idle = snap.run is None
        rows = [
            self._row("Chaves do Switch", "prod.keys guardado." if snap.keys_ok else "Nenhum prod.keys.",
                      t.button("Trocar prod.keys", self._keys, primary=False, icon_name="key-round")),
            self._row("Eventos", f"{self.service.event_count('swsh')} de Sword/Shield, "
                                 f"{self.service.event_count('frlg')} de FireRed/LeafGreen. {self.download_line}",
                      t.button("Baixar de novo", self._download, primary=False, icon_name="download",
                               disabled=not idle)),
            self._row(f"Versão {__version__}", UPDATE_TEXT.get(snap.update_state, ""),
                      t.button("Procurar atualização", self._check, primary=False, icon_name="refresh-cw")),
            self._row("Logs", str(self.service.cfg.logs_dir),
                      t.button("Abrir pasta", self._logs, primary=False, icon_name="folder-open")),
        ]
        credits = t.card(ft.Column([t.text("Créditos", 14, bold=True)] + [
            ft.Row([t.muted(label, 12), ft.Container(t.text(url, 12, t.ACCENT), on_click=lambda e, u=url: self._open(u))],
                   spacing=6, wrap=True) for label, url in CREDITS], spacing=6))
        self.control.controls = [t.text("Ajustes", 22, bold=True), *rows, credits]

    def _row(self, title: str, detail: str, action: ft.Control) -> ft.Container:
        return t.card(ft.Row([ft.Column([t.text(title, 14, bold=True), t.muted(detail, 12)], spacing=2, expand=True),
                              action], spacing=12))

    async def _keys(self, e) -> None:
        await choose_keys(self.shell)

    def _download(self, e) -> None:
        def line(text):
            self.download_line = text
            self.shell.ui(self.shell.render)
        download_events(self.shell, line)

    def _check(self, e) -> None:
        self.shell.toast("Procurando atualização…")
        self.shell.in_thread(self.service.check_update)

    def _logs(self, e) -> None:
        self.service.cfg.logs_dir.mkdir(parents=True, exist_ok=True)
        if IS_ANDROID:      # sem explorador de arquivos: o caminho já aparece na linha
            self.shell.toast(str(self.service.cfg.logs_dir))
            return
        os.startfile(self.service.cfg.logs_dir)

    def _open(self, url: str) -> None:
        self.shell.page.run_task(self.shell.launcher.launch_url, url)
