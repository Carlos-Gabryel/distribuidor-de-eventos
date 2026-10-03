"""Configuração e caminhos do Windows: os dados do usuário ficam em %LOCALAPPDATA%\\Distribuidor."""
from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "Distribuidor"
PROJECT_DIR = Path(__file__).resolve().parent.parent


def resource_root() -> Path:
    """Onde estão o pokeldn, os firmwares e os assets: a pasta do .exe extraído, ou o repositório."""
    return Path(getattr(sys, "_MEIPASS", PROJECT_DIR))


def default_data_dir() -> Path:
    if override := os.environ.get("DISTRIB_DATA_DIR"):
        return Path(override)
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / APP_NAME if base else Path.home() / f".{APP_NAME.lower()}"


@dataclass(frozen=True)
class Config:
    data_dir: Path
    pokeldn_dir: Path
    firmware_dir: Path
    keys: Path
    catalog_dir: Path
    state_dir: Path
    logs_dir: Path
    sprites_dir: Path
    frlg_idle_timeout: int


def load(data_dir: Path | None = None, root: Path | None = None) -> Config:
    data_dir = data_dir or default_data_dir()
    root = root or resource_root()
    settings: dict = {}
    file = data_dir / "config.toml"
    if file.exists():
        settings = tomllib.loads(file.read_text(encoding="utf-8"))
    return Config(
        data_dir=data_dir,
        pokeldn_dir=root / "vendor" / "pokeldn",
        firmware_dir=root / "firmware",
        keys=data_dir / "prod.keys",
        catalog_dir=data_dir / "catalog",
        state_dir=data_dir / "state",
        logs_dir=data_dir / "logs",
        sprites_dir=data_dir / "sprites",
        frlg_idle_timeout=int(settings.get("frlg_idle_timeout", 120)),
    )
