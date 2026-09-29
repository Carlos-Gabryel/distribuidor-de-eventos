"""Configuração: config.toml (versionado) + config.local.toml (por máquina, ignorado pelo git)."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    project_dir: Path
    pokeldn_dir: Path
    python: Path
    keys: Path
    catalog_dir: Path
    state_dir: Path
    logs_dir: Path
    frlg_idle_timeout: int


def _user_home() -> Path:
    # Rodando como root (wsl -u root), Path.home() seria /root; o launcher passa a home certa.
    return Path(os.environ.get("DISTRIB_USER_HOME") or Path.home())


def _path(value: str, base: Path) -> Path:
    if value.startswith("~"):
        return _user_home() / value[1:].lstrip("/")
    path = Path(value)
    return path if path.is_absolute() else base / path


def load(project_dir: Path = PROJECT_DIR) -> Config:
    data: dict = {}
    for name in ("config.toml", "config.local.toml"):
        file = project_dir / name
        if file.exists():
            data.update(tomllib.loads(file.read_text(encoding="utf-8")))
    return Config(
        project_dir=project_dir,
        pokeldn_dir=_path(data["pokeldn_dir"], project_dir),
        python=_path(data["python"], project_dir),
        keys=_path(data["keys"], project_dir),
        catalog_dir=_path(data.get("catalog_dir", "catalog"), project_dir),
        state_dir=_path(data.get("state_dir", "state"), project_dir),
        logs_dir=_path(data.get("logs_dir", "logs"), project_dir),
        frlg_idle_timeout=int(data.get("frlg_idle_timeout", 120)),
    )
