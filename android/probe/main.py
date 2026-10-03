import os
import sys

import flet as ft


def main(page: ft.Page):
    page.title = "distrib-probe"
    out = ft.Text(selectable=True, size=12)

    def ping(e):
        lines = [f"sys.version: {sys.version}", f"sys.platform: {sys.platform}"]
        for k in sorted(os.environ):
            if "FLET" in k.upper() or "ANDROID" in k.upper():
                # valor só de caminhos; das demais, só o nome (pode haver token)
                shown = os.environ[k] if ("STORAGE" in k or k in ("ANDROID_DATA", "ANDROID_ROOT")) else "<oculto>"
                lines.append(f"{k}={shown}")
        lines.append(f"cwd: {os.getcwd()}")
        out.value = (out.value + "\n\n" if out.value else "") + "\n".join(lines)
        page.update()

    page.add(
        ft.SafeArea(
            ft.Column(
                [ft.Button("ping", on_click=ping), out],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            expand=True,
        )
    )


ft.run(main)
