"""Caixas de sprite: Poké Ball apagada até o sprite chegar (do cache ou baixado numa thread)."""
from __future__ import annotations

import flet as ft


class SpriteSlots:
    def __init__(self, shell, size: int):
        self.shell, self.size = shell, size
        self._slots: dict[int, list[ft.Container]] = {}

    def box(self, species: int) -> ft.Container:
        box = ft.Container(width=self.size, height=self.size, alignment=ft.Alignment.CENTER)
        path = self.shell.service.sprites.cached(species)
        box.content = self._image(path.read_bytes()) if path else self._placeholder()
        if path is None and species > 0:
            self._slots.setdefault(species, []).append(box)
        return box

    def _placeholder(self) -> ft.Control:
        return ft.Image(src="pokeball.svg", width=self.size // 3, height=self.size // 3, opacity=0.25)

    def _image(self, data: bytes) -> ft.Image:
        return ft.Image(src=data, width=self.size, height=self.size, filter_quality=ft.FilterQuality.NONE)

    def load(self) -> None:
        """Baixa numa thread os sprites que faltam e troca as caixas pela imagem."""
        pending, self._slots = self._slots, {}

        def work():
            for species, boxes in pending.items():
                path = self.shell.service.sprites.get(species)
                if path is None:
                    continue
                data = path.read_bytes()

                def apply(boxes=boxes, data=data):
                    for box in boxes:
                        box.content = self._image(data)
                        box.update()

                self.shell.ui(apply)

        self.shell.in_thread(work)
