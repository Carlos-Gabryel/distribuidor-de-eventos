"""Primeira abertura: prod.keys, eventos e placa. Cada passo fica verde quando pronto."""
from __future__ import annotations

from pathlib import Path

import flet as ft

from distrib.platform import IS_ANDROID
from ui import theme as t


async def choose_keys(shell) -> None:
    # No Android o seletor não dá caminho usável (content://): lê os bytes. No PC segue o caminho.
    files = await shell.picker.pick_files(allowed_extensions=["keys"], file_type=ft.FilePickerFileType.CUSTOM,
                                          with_data=IS_ANDROID)
    if not files:
        return
    try:
        picked = files[0]
        if IS_ANDROID and picked.bytes is None:
            raise ValueError("Não consegui ler o arquivo escolhido.")
        shell.service.set_keys(picked.bytes if IS_ANDROID else Path(picked.path))
        shell.toast("prod.keys guardado.")
    except (ValueError, OSError) as exc:
        shell.toast(str(exc))


def download_events(shell, on_line) -> None:
    def work():
        try:
            shell.service.download_catalog(on_line)
        except OSError as exc:
            on_line(f"Falhou: {exc}. Confira a internet e tente de novo.")
    shell.in_thread(work)


class InicioView:
    def __init__(self, shell):
        self.shell = shell
        self.downloading = False
        self.progress_text = t.muted("", 11)
        self.steps = ft.Column(spacing=10)
        self.control = ft.Column([t.text("Vamos preparar o Distribuidor", 22, bold=True),
                                  t.muted("Três passos. Você só faz isso uma vez."),
                                  ft.Container(height=8), self.steps], spacing=6)

    def show(self, snap) -> None:
        self.update(snap)

    def update(self, snap) -> None:
        if snap.catalog_ok:
            self.downloading = False
        self.steps.controls = [
            self._step(1, "Suas chaves do Switch (prod.keys)", snap.keys_ok,
                       "Guardado." if snap.keys_ok else "Escolha o prod.keys extraído do seu próprio console.",
                       t.button("Escolher prod.keys", self._keys, icon_name="key-round",
                                primary=not snap.keys_ok)),
            self._step(2, "Eventos do Events Gallery", snap.catalog_ok,
                       "Baixados." if snap.catalog_ok else "Cerca de 56 MB, uma vez só.",
                       t.button("Baixando…" if self.downloading else "Baixar eventos", self._download,
                                icon_name="download", disabled=self.downloading or snap.catalog_ok),
                       extra=ft.Column([ft.ProgressBar(color=t.ACCENT, bgcolor=t.FIELD),
                                        self.progress_text], spacing=4) if self.downloading else None),
            self._step(3, "Placa conectada", snap.board.ok, snap.board.message,
                       t.button("Abrir a aba Placa", lambda e: self.shell.navigate("placa"),
                                icon_name="usb", primary=False)),
        ]

    def _step(self, number, title, done, detail, action, extra=None) -> ft.Container:
        badge = ft.Container(t.icon("check", 14, "#FFFFFF") if done else t.text(str(number), 12, bold=True),
                             width=26, height=26, border_radius=13, alignment=ft.Alignment.CENTER,
                             bgcolor=t.GREEN if done else t.HOVER)
        column = ft.Column([t.text(title, 14, bold=True), t.muted(detail, 12)], spacing=2, expand=True)
        if extra is not None:
            column.controls.append(extra)
        return t.card(ft.Row([badge, column, action], spacing=14), padding=14)

    async def _keys(self, e) -> None:
        await choose_keys(self.shell)

    def _download(self, e) -> None:
        self.downloading = True

        def line(text):
            self.shell.ui(lambda: (setattr(self.progress_text, "value", text), self.shell.render()))

        download_events(self.shell, line)
        self.shell.render()
