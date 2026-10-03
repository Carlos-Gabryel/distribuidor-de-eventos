import flet as ft

from ui import theme as t


class Placeholder:
    def __init__(self, shell, title: str):
        self.control = ft.Column([t.text(title, 20, bold=True), t.muted("Em construção")])

    def show(self, snap) -> None:
        pass

    def update(self, snap) -> None:
        pass
