import os
import sys
import threading
import traceback

import flet as ft


SEP = chr(10) * 2
BUSY = threading.Lock()  # um botão por vez: dois abrindo a placa brigam pela interface USB


def _faulthandler():
    """Crash nativo (SIGSEGV/SIGABRT) grava o traceback de todas as threads em crash.log.
    O log anterior vira crash.log.prev ao abrir, para o botão "último log" mostrar."""
    import faulthandler
    d = os.environ.get("FLET_APP_STORAGE_DATA") or os.getcwd()
    p = os.path.join(d, "crash.log")
    try:
        if os.path.exists(p) and os.path.getsize(p):
            os.replace(p, p + ".prev")
        f = open(p, "w")
        faulthandler.enable(file=f, all_threads=True)
        return f
    except Exception:
        return None


_CRASH_FILE = _faulthandler()


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

    def run_op(name):
        def start(e):
            def work():
                try:
                    import probe_ops
                    text = getattr(probe_ops, name)()
                except BaseException:
                    text = f"{name} FALHOU:" + chr(10) + traceback.format_exc()
                out.value = (out.value + SEP if out.value else "") + f"[{name}] {text}"
                page.update()

            if not BUSY.acquire(blocking=False):
                out.value = (out.value + SEP if out.value else "") + f"[{name}] ocupado: espere o anterior terminar"
                page.update()
                return
            out.value = (out.value + SEP if out.value else "") + f"[{name}] rodando..."
            page.update()

            def guarded():
                try:
                    work()
                finally:
                    BUSY.release()

            threading.Thread(target=guarded, daemon=True).start()

        return start

    page.add(
        ft.SafeArea(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Button("ping", on_click=ping),
                            ft.Button("último log", on_click=run_op("ultimo_log")),
                            ft.Button("HELLO", on_click=run_op("hello")),
                            ft.Button("BENCH", on_click=run_op("bench")),
                            ft.Button("unicorn", on_click=run_op("unicorn_test")),
                            ft.Button("chip", on_click=run_op("chip")),
                            ft.Button("gravar", on_click=run_op("gravar")),
                            ft.Button("gravar (trace)", on_click=run_op("gravar_trace")),
                            ft.Button("gravar (ROM)", on_click=run_op("gravar_rom")),
                        ],
                        wrap=True,
                    ),
                    out,
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            expand=True,
        )
    )


ft.run(main)
