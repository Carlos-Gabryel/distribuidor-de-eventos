"""Placa: estado, porta, ponte USB, "Preparar placa" (grava o firmware) e drivers."""
from __future__ import annotations

import flet as ft

from distrib import radio
from ui import theme as t


class PlacaView:
    def __init__(self, shell):
        self.shell, self.service = shell, shell.service
        self.control = ft.Column(expand=True, spacing=t.GAP)

    def show(self, snap) -> None:
        self.update(snap)

    def update(self, snap) -> None:
        board, flashing = snap.board, snap.flash_progress is not None
        can_flash = snap.run is None and not flashing and board.kind not in ("none", "many")
        info = t.card(ft.Column([
            ft.Row([t.dot(t.GREEN if board.ok else t.ACCENT), t.text(t.BOARD_TITLES.get(board.kind, board.kind), 15, bold=True)],
                   spacing=8),
            t.muted(board.message),
            ft.Row([t.muted(f"Porta: {board.port or '—'}"), t.muted(f"Ponte USB: {board.bridge or '—'}")], spacing=24),
            ft.Row([t.button("Preparar placa", self._ask_flash, icon_name="zap", disabled=not can_flash),
                    t.button("Testar de novo", self._recheck, primary=False, icon_name="refresh-cw",
                             disabled=flashing or snap.run is not None)], spacing=10),
            t.muted("Preparar placa grava o firmware do pokeldn. Faça isso numa placa nova ou se ela "
                    "parar de responder.", 11),
        ], spacing=10))
        controls = [t.text("Placa", 22, bold=True), info]
        if flashing:
            controls.append(t.card(ft.Column([
                ft.ProgressBar(value=snap.flash_progress, color=t.ACCENT, bgcolor=t.FIELD),
                ft.ListView([ft.Text(line, size=11, font_family="Consolas", color=t.MUTED)
                             for line in snap.log[-60:]], height=180, auto_scroll=True)], spacing=8)))
        if board.kind == "none":
            controls.append(self._drivers())
        self.control.controls = controls

    def _drivers(self) -> ft.Container:
        links = [t.button(name, lambda e, url=url: self._open(url), primary=False, icon_name="external-link")
                 for name, url in radio.DRIVERS.items()]
        return t.card(ft.Column([
            t.text("A placa está plugada e não aparece?", 14, bold=True),
            t.muted("Instale o driver do chip USB da sua placa (vem escrito perto do conector: "
                    "CP2102, CH340 ou CH9102) e replugue o cabo. Use um cabo de dados, não só de carga."),
            ft.Row(links, spacing=8, wrap=True)], spacing=8))

    def _open(self, url: str) -> None:
        self.shell.page.run_task(self.shell.launcher.launch_url, url)

    def _recheck(self, e=None) -> None:
        self.shell.in_thread(self.service.check_board, True)

    def _ask_flash(self, e=None) -> None:
        def close(e=None):
            self.shell.page.pop_dialog()

        def confirm(e=None):
            close()
            self.shell.in_thread(self._flash)

        self.shell.page.show_dialog(ft.AlertDialog(
            modal=True, bgcolor=t.CARD,
            title=t.text("Preparar a placa?", 16, bold=True),
            content=t.muted("O firmware do pokeldn será gravado e o que estiver na placa será apagado. "
                            "Não desplugue o cabo até terminar (cerca de 30 segundos)."),
            actions=[t.button("Cancelar", close, primary=False), t.button("Gravar", confirm, icon_name="zap")]))

    def _flash(self) -> None:
        try:
            code = self.service.flash_board()
        except RuntimeError as exc:
            self.shell.toast(str(exc))
            return
        self.shell.toast("Placa preparada." if code == 0 else
                         "A gravação falhou. Veja o log, replugue a placa e tente de novo.")
