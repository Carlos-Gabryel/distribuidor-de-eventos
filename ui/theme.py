"""Tokens visuais e componentes base. Tema escuro, um destaque (vermelho Poké Ball)."""
from __future__ import annotations

import flet as ft

from distrib.platform import IS_ANDROID

BG, SIDEBAR, CARD, FIELD, HOVER = "#0E0F12", "#14161A", "#16181D", "#1A1D22", "#1F2329"
BORDER, TEXT, MUTED, FAINT = "#23252B", "#E8E9EC", "#9AA0AA", "#6B717B"
ACCENT, GREEN, AMBER = "#E8445A", "#3DD68C", "#F5A524"
RADIUS, RADIUS_SMALL, GAP, SIDEBAR_WIDTH, CONTROL_HEIGHT = 12, 8, 12, 220, 36

BOARD_TITLES = {"ready": "Placa pronta", "checking": "Procurando a placa", "none": "Sem placa",
                "many": "Várias placas", "busy": "Placa ocupada", "silent": "Placa sem resposta",
                "flashing": "Gravando firmware"}
BOARD_COLORS = {"ready": GREEN, "checking": AMBER, "flashing": AMBER}


def text(value: str, size: int = 13, color: str = TEXT, bold: bool = False, **kw) -> ft.Text:
    return ft.Text(value, size=size, color=color, weight=ft.FontWeight.W_600 if bold else None, **kw)


def muted(value: str, size: int = 12, **kw) -> ft.Text:
    return text(value, size=size, color=MUTED, **kw)


def icon(name: str, size: int = 18, color: str = MUTED) -> ft.Image:
    return ft.Image(src=f"icons/{name}.svg", width=size, height=size, color=color,
                    color_blend_mode=ft.BlendMode.SRC_IN)


def border(color: str = BORDER, width: int = 1) -> ft.Border:
    side = ft.BorderSide(width, color)
    return ft.Border(top=side, right=side, bottom=side, left=side)


def card(content: ft.Control, padding: int = 14, on_click=None, selected: bool = False,
         **kw) -> ft.Container:
    return ft.Container(content=content, padding=padding, bgcolor=CARD, border_radius=RADIUS,
                        border=border(ACCENT if selected else BORDER), on_click=on_click,
                        ink=on_click is not None, **kw)


def button(label: str, on_click=None, primary: bool = True, icon_name: str | None = None,
           disabled: bool = False) -> ft.Button:
    ink = "#FFFFFF" if primary else TEXT
    style = ft.ButtonStyle(
        bgcolor={ft.ControlState.DISABLED: HOVER, ft.ControlState.DEFAULT: ACCENT if primary else HOVER},
        color={ft.ControlState.DISABLED: FAINT, ft.ControlState.DEFAULT: ink},
        shape=ft.StadiumBorder(), padding=ft.Padding(18, 8, 18, 8), elevation=0,
        text_style=ft.TextStyle(size=13, weight=ft.FontWeight.W_600))
    return ft.Button(label, icon=icon(icon_name, 16, ink) if icon_name else None,
                     on_click=on_click, style=style, disabled=disabled, height=CONTROL_HEIGHT)


def dot(color: str) -> ft.Container:
    return ft.Container(width=8, height=8, border_radius=4, bgcolor=color)


def board_card(info, compact: bool = False) -> ft.Container:
    color = BOARD_COLORS.get(info.kind, ACCENT)
    bad = color == ACCENT
    if compact:     # faixa do topo no celular: marca à esquerda, pílula do estado da placa à direita
        pill = ft.Container(
            padding=ft.Padding(10, 4, 10, 4), border_radius=999, bgcolor="#2A1519" if bad else HOVER,
            border=border("#5A2630" if bad else BORDER),
            content=ft.Row([dot(color), text(BOARD_TITLES.get(info.kind, info.kind), 11, bold=True)],
                           spacing=6, tight=True))
        return ft.Container(
            padding=ft.Padding(12, 8, 12, 8), bgcolor=CARD, border=ft.Border(bottom=ft.BorderSide(1, BORDER)),
            content=ft.Row([brand(), pill], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
    return ft.Container(
        padding=10, border_radius=RADIUS_SMALL, bgcolor="#2A1519" if bad else CARD,
        border=border("#5A2630" if bad else BORDER),
        content=ft.Column([ft.Row([dot(color), text(BOARD_TITLES.get(info.kind, info.kind), 12, bold=True)],
                                  spacing=6),
                           muted(info.message, 11)], spacing=4))


def brand() -> ft.Row:
    return ft.Row([ft.Image(src="pokeball.svg", width=22, height=22),
                   text("Distribuidor", 15, bold=True)], spacing=8)


def nav_item(label: str, icon_name: str, selected: bool, on_click) -> ft.Container:
    color = TEXT if selected else MUTED
    return ft.Container(content=ft.Row([icon(icon_name, 16, color), text(label, 13, color)], spacing=10),
                        padding=ft.Padding(10, 8, 10, 8), border_radius=RADIUS_SMALL,
                        bgcolor=HOVER if selected else None, on_click=on_click, ink=True)


def crumbs(parts: list[tuple[str, object]]) -> ft.Row:
    """[(rótulo, on_click ou None)]; o último é a etapa atual."""
    items: list[ft.Control] = []
    for index, (label, on_click) in enumerate(parts):
        if index:
            items.append(muted("›", 12))
        last = index == len(parts) - 1
        # uma linha só: a etapa atual ocupa o que sobra e corta com reticências
        items.append(ft.Container(text(label, 12, TEXT if last else MUTED, bold=last, max_lines=1,
                                       overflow=ft.TextOverflow.ELLIPSIS, no_wrap=True),
                                  on_click=None if last else on_click, expand=last))
    return ft.Row(items, spacing=6)


def stat(label: str, value: str) -> ft.Container:
    return card(ft.Column([muted(label, 11), text(value, 20, bold=True)], spacing=2), padding=12, expand=True)


def apply_page(page: ft.Page) -> None:
    page.title = "Distribuidor de Eventos"
    page.bgcolor = BG
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(color_scheme=ft.ColorScheme(primary=ACCENT, surface=CARD))
    page.padding = 0
    if IS_ANDROID:      # sem janela: tela cheia do celular
        return
    page.window.title_bar_hidden = True
    page.window.title_bar_buttons_hidden = True
    page.window.width, page.window.height = 1180, 760
    page.window.min_width, page.window.min_height = 960, 620
