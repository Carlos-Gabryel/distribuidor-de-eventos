"""FireRed/LeafGreen: um console por sessão, pelo nosso runner (distrib.runners.frlg_session)."""
from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

from distrib.catalog import Catalog, Event, save_index
from distrib.config import Config
from distrib.games.base import Job, Update

FRLG_RAW = "Released/Gen 3"
LANGUAGES = {1: "JPN", 2: "ENG", 3: "FRE", 4: "ITA", 5: "GER", 7: "SPA"}
EXTRAS = (
    ("altering-cave", "Altering Cave (evento oficial)", "Muda os Pokémon da Altering Cave"),
    ("battle-count-card", "Battle Count Card (oficial)", "Cartão que conta batalhas e trocas"),
    ("beast-cutscene-share", "Cena da fera lendária", "Cena repetível da fera lendária"),
    ("celebi", "Celebi Nv50 (montado pelo pokeldn)", "Celebi entregue pelo entregador"),
    ("porygon-tm-gift", "Porygon + TMs", "Porygon, cena da Clefairy, TM29 e TM46"),
    ("solrock-stamp", "Stamp Rally: Solrock", "Metade Solrock do Sun and Moon Rally"),
    ("lunatone-stamp", "Stamp Rally: Lunatone", "Metade Lunatone do Sun and Moon Rally"),
    ("master-ball", "Master Ball", "Uma Master Ball pelo entregador"),
    ("worlds-xp", "Worlds 26 (FANtastic Mystery Gift)", "Presente do Worlds 26"),
    ("visiting-trainer", "Treinador visitante (só FireRed)", "Treinador da Battle Tower"),
)
_PREFIX = re.compile(r"^[A-Z]+ - ")
_PID_TAG = re.compile(r" \([0-9A-Fa-f]{4,8}\)")
_STATUS = re.compile(r"Mystery Event script status: (\d+)")
_HOSTING = re.compile(r"Hosting\. Waiting for the console to join .*channel (\d+)")
_CONSOLE = ("joined",)          # a prova de conceito (Task 2) confirma ou troca este texto


def event_name(path: Path) -> str:
    return _PID_TAG.sub("", _PREFIX.sub("", path.stem)).strip()


def _shiny(d: dict) -> bool:
    tid, sid, pid = d["otid"] & 0xFFFF, d["otid"] >> 16, d["pid"]
    return (tid ^ sid ^ (pid >> 16) ^ (pid & 0xFFFF)) < 8


class Rotation:
    """Qual variante de PID sai na próxima entrega de cada evento (salvo em disco)."""

    def __init__(self, path: Path | None):
        self.path = path
        try:
            self._next = json.loads(path.read_text(encoding="utf-8")) if path else {}
        except (OSError, ValueError):
            self._next = {}

    def next_file(self, event: Event) -> str:
        index = self._next.get(event.key, 0) % len(event.files)
        self._next[event.key] = index + 1
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._next, ensure_ascii=False), encoding="utf-8")
        return event.files[index]


class FrlgAdapter:
    game = "frlg"
    title = "FireRed/LeafGreen"
    mode = "session"
    instructions = "No jogo: MYSTERY GIFT → WONDER CARDS → FRIEND (um console por vez)"

    def __init__(self, rotation_path: Path | None = None):
        self.rotation = Rotation(rotation_path)

    def build_catalog(self, raw_dir: Path, cfg: Config) -> Catalog:
        from distrib.frlg_gift import GiftError, load_mon
        out = cfg.catalog_dir / self.game
        out.mkdir(parents=True, exist_ok=True)
        catalog = Catalog(self.game)
        groups: dict[str, list[tuple[Path, dict]]] = defaultdict(list)
        for path in sorted(raw_dir.rglob("*.pk3")):
            try:
                mon = load_mon(path)
            except GiftError:
                catalog.invalid += 1
                continue
            folder = path.parent.relative_to(raw_dir).as_posix()
            groups[f"{folder}/{event_name(path)}"].append((path, mon.decode()))
        for number, (key, members) in enumerate(sorted(groups.items())):
            files = []
            for variant, (path, _) in enumerate(members):
                name = f"{number:05d}-{variant:03d}.pk3"
                shutil.copyfile(path, out / name)
                files.append(name)
            catalog.events.append(self._event(key, members, tuple(files)))
        for slug, name, description in EXTRAS:
            catalog.events.append(Event(
                game=self.game, key=f"extra:{slug}", name=name, kind="extra",
                details=(("Tipo", "presente do pokeldn"), ("O que faz", description)),
                files=(), sort_key=f"~{name}"))
        save_index(catalog, out / "index.json")
        return catalog

    def _event(self, key: str, members: list, files: tuple[str, ...]) -> Event:
        folder, _, name = key.rpartition("/")
        d = members[0][1]
        shiny = sum(_shiny(m[1]) for m in members)
        details = (("Espécie", d["nickname"]), ("Nível", str(d["level"])),
                   ("OT", d["otName"]), ("TID", str(d["otid"] & 0xFFFF)),
                   ("Idioma", LANGUAGES.get(d["language"], str(d["language"]))),
                   ("Variantes (PID)", str(len(files))),
                   ("Shiny", f"{shiny} de {len(files)} variantes"),
                   ("Pasta", folder))
        return Event(game=self.game, key=key, name=name, kind="pokemon", details=details,
                     files=files, sort_key=name)

    def build_job(self, event: Event, cfg: Config, port: str) -> Job:
        argv = [str(cfg.python), "-u", "-m", "distrib.runners.frlg_session",
                "--pokeldn", str(cfg.pokeldn_dir)]
        if event.kind == "extra":
            argv += ["--extra", event.key.removeprefix("extra:")]
        else:
            argv += ["--pk3", str(cfg.catalog_dir / self.game / self.rotation.next_file(event))]
        argv += ["--keys", str(cfg.keys), "--phy", "auto",
                 "--idle-timeout", str(cfg.frlg_idle_timeout)]
        return Job(argv=tuple(argv), env={"POKELDN_RADIO": f"esp32:{port}"},
                   cwd=str(cfg.project_dir), label=event.name)

    def parse_line(self, line: str) -> Update | None:
        if line.startswith("[distrib] presente "):
            return Update(detail=line.split(": ", 1)[1].strip())
        if match := _HOSTING.search(line):
            return Update(state="on_air", channel=int(match.group(1)))
        if match := _STATUS.search(line):
            code = int(match.group(1))
            return Update(state={2: "delivered", 3: "party_full"}.get(code, "not_delivered"))
        if " delivered. On the Switch" in line:
            return Update(state="delivered")
        if line.startswith("Session finished without delivering anything"):
            return Update(state="not_delivered", detail=line.strip())
        if any(text in line for text in _CONSOLE):
            return Update(state="console")
        if line.startswith(("RuntimeError", "Traceback", "OSError", "PermissionError")):
            return Update(state="error", detail=line.strip())
        return None
