"""Processos-filho do próprio app.

O .exe (ou o Python, no desenvolvimento) se chama de novo com `--run <script do pokeldn>` ou
`--module <módulo>`. Um processo sem janela no Windows não recebe Ctrl+C: o pai fecha o stdin e,
com DISTRIB_MANAGED_RUN=1, o filho transforma esse fim de arquivo em KeyboardInterrupt, que é
como os hosts do pokeldn desmontam a rede na placa.
"""
from __future__ import annotations

import signal
import os
import runpy
import subprocess
import sys
import threading
from pathlib import Path

from distrib.config import PROJECT_DIR
from distrib.platform import IS_ANDROID
from distrib.pokeldn_path import ensure_importable

MANAGED = "DISTRIB_MANAGED_RUN"
MODES = ("--run", "--module")

if IS_ANDROID:
    from distrib.platform import inproc
    popen, run = inproc.InProcPopen, inproc.run
else:
    popen, run = subprocess.Popen, subprocess.run


def command(*argv: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, *argv]
    return [sys.executable, "-u", str(PROJECT_DIR / "main.py"), *argv]


def child_env(extra: dict[str, str] | None = None, managed: bool = True) -> dict[str, str]:
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8", **(extra or {})}
    if managed:
        env[MANAGED] = "1"
    else:
        env.pop(MANAGED, None)
    return env


def popen_kwargs() -> dict:
    return dict(stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)


def is_child(argv: list[str]) -> bool:
    return len(argv) >= 2 and argv[0] in MODES


def _interrupt_on_stdin_close() -> None:
    try:
        sys.stdin.read()
    except (OSError, ValueError):
        pass
    signal.raise_signal(signal.SIGINT)


def child(argv: list[str], pokeldn_dir: Path, inproc: bool = False) -> None:
    """`inproc=True`: roda numa thread do app; sem reconfigure do stdout nem thread do stdin."""
    if not inproc:
        for stream in (sys.stdout, sys.stderr):
            if stream is not None:
                stream.reconfigure(encoding="utf-8", line_buffering=True)
    if not inproc and sys.stdin is not None and os.environ.get(MANAGED):
        threading.Thread(target=_interrupt_on_stdin_close, daemon=True).start()
    if inproc and IS_ANDROID:       # idempotente; o app já aplicou no início
        from distrib import config
        from distrib.platform import android_env
        android_env.apply(config.load())
    ensure_importable(pokeldn_dir)
    mode, target, *args = argv
    radio_spec = os.environ.get("POKELDN_RADIO", "")
    if radio_spec.startswith("esp32:") and target != "distrib.runners.hello":
        from distrib.runners import quiet
        try:
            quiet.quiet(radio_spec.removeprefix("esp32:"))
        except Exception as exc:          # o host tenta mesmo assim e reporta o erro dele
            print(f"[quiet] erro: {exc}", flush=True)
    if mode == "--run":
        path = pokeldn_dir / target
        sys.argv = [str(path), *args]
        sys.path.insert(0, str(path.parent))
        runpy.run_path(str(path), run_name="__main__")
    else:
        sys.argv = [target, *args]
        runpy.run_module(target, run_name="__main__", alter_sys=True)
