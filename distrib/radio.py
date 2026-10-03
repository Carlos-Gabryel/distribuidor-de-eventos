"""A placa: achar a porta COM e fazer o HELLO (num processo-filho, como os hosts)."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from serial.tools import list_ports

from distrib import runner
from distrib.config import Config

BRIDGES = {
    (0x10C4, 0xEA60): "CP210x",
    (0x1A86, 0x7523): "CH340",
    (0x1A86, 0x55D4): "CH9102",
    (0x0403, 0x6001): "FT232R",
    (0x303A, 0x1001): "USB nativo do ESP32",
}
DRIVERS = {
    "CP210x": "https://www.silabs.com/developer-tools/usb-to-uart-bridge-vcp-drivers",
    "CH340": "https://www.wch-ic.com/downloads/CH341SER_EXE.html",
    "CH9102": "https://www.wch-ic.com/downloads/CH343SER_EXE.html",
}


class RadioError(Exception):
    pass


@dataclass(frozen=True)
class Port:
    device: str
    bridge: str


def list_boards(comports=list_ports.comports) -> list[Port]:
    found = [Port(p.device, BRIDGES.get((p.vid, p.pid), "desconhecida"))
             for p in comports() if p.vid is not None]
    return sorted(found, key=lambda p: p.device)


def find_port(comports=list_ports.comports) -> str | None:
    boards = list_boards(comports)
    return boards[0].device if len(boards) == 1 else None


def hello(port: str, cfg: Config, run=subprocess.run) -> str:
    try:
        done = run(runner.command("--module", "distrib.runners.hello", port),
                   cwd=str(cfg.pokeldn_dir), env=runner.child_env(managed=False),
                   stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=20,
                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except subprocess.TimeoutExpired as exc:
        raise RadioError(f"a placa em {port} não respondeu em 20 s") from exc
    if done.returncode != 0:
        lines = done.stderr.strip().splitlines() or done.stdout.strip().splitlines()
        raise RadioError(f"HELLO falhou em {port}: {(lines or ['erro desconhecido'])[-1]}")
    return done.stdout.strip().splitlines()[-1]
