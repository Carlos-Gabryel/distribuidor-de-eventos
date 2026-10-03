"""Grava o firmware do pokeldn: python main.py --module distrib.runners.flash COM5 PASTA"""
import sys
from pathlib import Path

import esptool

from distrib.board import CHIP_ARG, BoardError, firmware_for


def main(argv=None) -> int:
    port, folder = (argv if argv is not None else sys.argv[1:])[:2]
    with esptool.detect_chip(port, connect_attempts=2) as chip:
        name = chip.CHIP_NAME
    print(f"[flash] chip {name}", flush=True)
    try:
        path = firmware_for(name, Path(folder))
    except BoardError as exc:
        print(f"[flash] erro: {exc}", flush=True)
        return 2
    esptool.main(["--chip", CHIP_ARG[name], "--port", port, "--baud", "460800",
                  "--after", "hard-reset", "write-flash", "0x0", str(path)])
    print("[flash] ok", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
