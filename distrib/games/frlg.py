"""FireRed/LeafGreen: um console por sessão, pelo nosso runner (distrib.runners.frlg_session)."""
from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

from distrib import runner
from distrib.catalog import Catalog, Event, save_index
from distrib.config import Config
from distrib.games.base import Job, Update
from distrib.species import gen3_to_national

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
_STATUS = re.compile(r"Mystery Event script status: (\d+)")
_HOSTING = re.compile(r"Hosting\. Waiting for the console to join .*channel (\d+)")
_CONSOLE = ("A console joined the network",)   # linha real da prova de conceito (2026-09-28)


def _shiny(d: dict) -> bool:
    tid, sid, pid = d["otid"] & 0xFFFF, d["otid"] >> 16, d["pid"]
    return (tid ^ sid ^ (pid >> 16) ^ (pid & 0xFFFF)) < 8


class Rotation:
    """Qual variante de PID sai na próxima entrega de cada evento (salvo em disco).

    Só avança quando uma entrega é confirmada: sessões sem console ou sem entrega repetem o PID.
    """

    def __init__(self, path: Path | None):
        self.path = path
        try:
            self._next = json.loads(path.read_text(encoding="utf-8")) if path else {}
        except (OSError, ValueError):
            self._next = {}

    def peek(self, event: Event) -> str:
        return event.files[self._next.get(event.key, 0) % len(event.files)]

    def advance(self, event: Event) -> None:
        self._next[event.key] = (self._next.get(event.key, 0) + 1) % len(event.files)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._next, ensure_ascii=False), encoding="utf-8")


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
        # Um evento = mesma pasta, espécie, OT e idioma. Nem o nome do arquivo (variantes numeradas
        # por PID "(1910)" ou contador "(001 of 430)") nem o TID (o PCNY dava um TID por pessoa).
        groups: dict[tuple, list[tuple[Path, dict]]] = defaultdict(list)
        for path in sorted(raw_dir.rglob("*.pk3")):
            try:
                mon = load_mon(path)
            except GiftError:
                catalog.invalid += 1
                continue
            folder = path.parent.relative_to(raw_dir).as_posix()
            d = mon.decode()
            groups[(folder, d["species"], d["otName"], d["language"])].append((path, d))
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

    def _event(self, key: tuple, members: list, files: tuple[str, ...]) -> Event:
        folder, species, ot, _ = key
        d = members[0][1]
        tids = {m[1]["otid"] & 0xFFFF for m in members}
        tid = str(tids.pop()) if len(tids) == 1 else f"vários ({len(tids)})"
        language = LANGUAGES.get(d["language"], str(d["language"]))
        name = f"{d['nickname']} ({d['otName']}, {language})"
        shiny = sum(_shiny(m[1]) for m in members)
        details = (("Espécie", d["nickname"]), ("Nível", str(d["level"])),
                   ("OT", d["otName"]), ("TID", tid), ("Idioma", language),
                   ("Variantes (PID)", str(len(files))),
                   ("Shiny", f"{shiny} de {len(files)} variantes"),
                   ("Pasta", folder))
        highlights = [f"Nv {d['level']}"]
        if shiny == len(files):
            highlights.append("Shiny")
        return Event(game=self.game, key=f"{folder}/{species}/{ot}/{d['language']}", name=name,
                     kind="pokemon", details=details, files=files, sort_key=name,
                     species=gen3_to_national(species), highlights=tuple(highlights),
                     region=language)

    def build_job(self, event: Event, cfg: Config, port: str) -> Job:
        argv = ["--module", "distrib.runners.frlg_session", "--pokeldn", str(cfg.pokeldn_dir)]
        on_delivered = None
        if event.kind == "extra":
            argv += ["--extra", event.key.removeprefix("extra:")]
        else:
            argv += ["--pk3", str(cfg.catalog_dir / self.game / self.rotation.peek(event))]
            on_delivered = lambda: self.rotation.advance(event)
        argv += ["--keys", str(cfg.keys), "--phy", "auto",
                 "--idle-timeout", str(cfg.frlg_idle_timeout)]
        return Job(argv=tuple(runner.command(*argv)), env={"POKELDN_RADIO": f"esp32:{port}"},
                   cwd=str(cfg.pokeldn_dir), label=event.name, on_delivered=on_delivered)

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
