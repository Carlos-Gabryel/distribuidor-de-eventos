"""Preparar a placa: escolher o firmware do pokeldn pelo chip e gravar num processo-filho."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Callable

from distrib import runner
from distrib.config import Config

FIRMWARE = {
    "ESP32": "pokeldn-radio.bin",
    "ESP32-S3": "pokeldn-radio-s3.bin",
    "ESP32-C3": "pokeldn-radio-c3.bin",
    "ESP32-C6": "pokeldn-radio-c6.bin",
}
CHIP_ARG = {"ESP32": "esp32", "ESP32-S3": "esp32s3", "ESP32-C3": "esp32c3", "ESP32-C6": "esp32c6"}
_PERCENT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s?%")


class BoardError(Exception):
    pass


def firmware_for(chip: str, firmware_dir: Path) -> Path:
    name = FIRMWARE.get(chip)
    if name is None:
        raise BoardError(f"{chip} não é suportado. Use ESP32, ESP32-S3, ESP32-C3 ou ESP32-C6.")
    path = firmware_dir / name
    if not path.is_file():
        raise BoardError(f"Falta o firmware {name} em {firmware_dir}")
    return path


def parse_progress(line: str) -> float | None:
    if "Writing at" not in line:
        return None
    match = _PERCENT.search(line)
    return min(float(match.group(1)), 100.0) / 100 if match else None


def flash(port: str, cfg: Config, on_line: Callable[[str], None],
          on_progress: Callable[[float], None], popen=None) -> int:
    popen = popen or runner.popen
    kwargs = {**runner.popen_kwargs(), "stdin": subprocess.DEVNULL}
    proc = popen(runner.command("--module", "distrib.runners.flash", port, str(cfg.firmware_dir)),
                 cwd=str(cfg.pokeldn_dir), env=runner.child_env(managed=False), **kwargs)
    for line in proc.stdout:
        line = line.rstrip("\n")
        on_line(line)
        if (value := parse_progress(line)) is not None:
            on_progress(value)
    return proc.wait()
