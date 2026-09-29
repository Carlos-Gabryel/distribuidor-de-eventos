"""Sword/Shield: Wonder Cards .wc8 anunciados pelo bin/swsh_gift_host.py (vários consoles de uma vez)."""
from __future__ import annotations

import re
from pathlib import Path

from distrib.catalog import Catalog, Event, save_index
from distrib.config import Config
from distrib.games.base import Job, Update

SWSH_RAW = "Released/Gen 8/SwSh/Wondercards"
SHINY = {0: "nunca", 1: "possível", 2: "sempre (estrela)", 3: "sempre (quadrado)",
         4: "fixo pelo PID"}
GAMES = {1: "Sword", 2: "Shield", 3: "Sword e Shield"}
_PREFIX = re.compile(r"^\d{4} (?:SWSH|SW|SH) - ")
_CHANNEL = re.compile(r"\[host\] AP up: .* ch=(\d+)")


def clean_name(path: Path, raw_dir: Path) -> str:
    name = _PREFIX.sub("", path.stem)
    parent = path.parent.relative_to(raw_dir)
    return f"{parent.as_posix()}: {name}" if str(parent) != "." else name


class SwshAdapter:
    game = "swsh"
    title = "Sword/Shield"
    mode = "broadcast"
    instructions = ("Nos consoles: Presente Misterioso → Receber presente → "
                    "Por comunicação local")

    def build_catalog(self, raw_dir: Path, cfg: Config) -> Catalog:
        from pokeldn.swsh import wc8
        out = cfg.catalog_dir / self.game
        out.mkdir(parents=True, exist_ok=True)
        catalog = Catalog(self.game)
        for index, path in enumerate(sorted(raw_dir.rglob("*.wc8"))):
            rec = path.read_bytes()
            if len(rec) != wc8.RECORD:
                catalog.invalid += 1
                continue
            if not wc8.sealed(rec):
                rec = bytes(wc8.seal(bytearray(rec)))
            info = wc8.read(rec)
            file_name = f"{index:04d}.wc8"
            (out / file_name).write_bytes(rec)
            catalog.events.append(self._event(info, clean_name(path, raw_dir), file_name))
        save_index(catalog, out / "index.json")
        return catalog

    def _event(self, info: dict, name: str, file_name: str) -> Event:
        pokemon = info["kind"] == 1
        details = [("Cartão", f"#{info['card_id']:04d}"),
                   ("Jogos", GAMES.get(info["region_mask"] & 3, "?"))]
        if pokemon:
            own_ids = info["tid"] == 0 and info["sid"] == 0
            details += [("Espécie", f"#{info['species']}"),
                        ("Nível", str(info["level"]) if info["level"] else "aleatório"),
                        ("Shiny", SHINY.get(info["shiny_type"], str(info["shiny_type"]))),
                        ("Gigantamax", "sim" if info["gigantamax"] else "não"),
                        ("OT", info["ot"] or "do jogador"),
                        ("TID/SID", "do jogador" if own_ids else f"{info['tid']}/{info['sid']}")]
        return Event(game=self.game, key=file_name, name=name,
                     kind="pokemon" if pokemon else "item", details=tuple(details),
                     files=(file_name,), sort_key=f"{info['card_id']:04d} {name}")

    def build_job(self, event: Event, cfg: Config, port: str) -> Job:
        record = cfg.catalog_dir / self.game / event.files[0]
        return Job(
            argv=(str(cfg.python), "-u", str(cfg.pokeldn_dir / "bin" / "swsh_gift_host.py"),
                  "--record", str(record), "--keys", str(cfg.keys),
                  "--seconds", "86400", "--no-validate"),
            env={"POKELDN_RADIO": f"esp32:{port}"},
            cwd=str(cfg.pokeldn_dir), label=event.name)

    def parse_line(self, line: str) -> Update | None:
        if match := _CHANNEL.search(line):
            return Update(channel=int(match.group(1)))
        if line.startswith("advertising comm id"):
            return Update(state="on_air")
        if line.startswith(("RuntimeError", "Traceback", "OSError", "PermissionError")):
            return Update(state="error", detail=line.strip())
        return None
