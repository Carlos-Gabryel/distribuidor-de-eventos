"""O contrato que cada jogo cumpre; as telas e o distributor só conhecem isto."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from distrib.catalog import Catalog, Event
from distrib.config import Config

STATES = ("on_air", "console", "delivered", "party_full", "not_delivered", "error")


@dataclass(frozen=True)
class Job:
    argv: tuple[str, ...]
    env: dict[str, str] = field(default_factory=dict)
    cwd: str = "."
    label: str = ""
    on_delivered: Callable[[], None] | None = None   # chamado a cada entrega confirmada


@dataclass(frozen=True)
class Update:
    state: str | None = None
    channel: int | None = None
    detail: str | None = None


class Adapter(Protocol):
    game: str
    title: str
    mode: str               # "broadcast" (SwSh) | "session" (FRLG)
    instructions: str

    def build_catalog(self, raw_dir: Path, cfg: Config) -> Catalog: ...

    def build_job(self, event: Event, cfg: Config, port: str) -> Job: ...

    def parse_line(self, line: str) -> Update | None: ...
