"""O catálogo de um jogo: eventos, busca, índice em JSON e a vitrine do dia (favoritos)."""
from __future__ import annotations

import json
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

INDEX_VERSION = 2


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


@dataclass(frozen=True)
class Event:
    game: str
    key: str
    name: str
    kind: str                                   # "pokemon" | "item" | "extra"
    details: tuple[tuple[str, str], ...]
    files: tuple[str, ...]
    sort_key: str
    species: int = 0                            # número nacional; 0 = não é Pokémon
    highlights: tuple[str, ...] = ()            # "Shiny", "Gigantamax", "Nv 60"…
    region: str = ""                            # "Ocidente", "Japão", "ENG"…

    @property
    def search_text(self) -> str:
        return normalize(" ".join([self.name, *(v for _, v in self.details)]))


@dataclass
class Catalog:
    game: str
    events: list[Event] = field(default_factory=list)
    invalid: int = 0

    def search(self, text: str = "", include_items: bool = False) -> list[Event]:
        words = normalize(text).split()
        found = [e for e in self.events
                 if (include_items or e.kind != "item")
                 and all(w in e.search_text for w in words)]
        return sorted(found, key=lambda e: e.sort_key)

    def get(self, key: str) -> Event:
        for event in self.events:
            if event.key == key:
                return event
        raise KeyError(key)


def save_index(catalog: Catalog, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"version": INDEX_VERSION, "game": catalog.game, "invalid": catalog.invalid,
            "events": [asdict(e) for e in catalog.events]}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def load_index(game: str, path: Path) -> Catalog:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version") != INDEX_VERSION:
            return Catalog(game)
        events = [Event(game=e["game"], key=e["key"], name=e["name"], kind=e["kind"],
                        details=tuple(tuple(d) for d in e["details"]),
                        files=tuple(e["files"]), sort_key=e["sort_key"],
                        species=int(e.get("species", 0)),
                        highlights=tuple(e.get("highlights", ())),
                        region=e.get("region", ""))
                  for e in data["events"]]
        return Catalog(game, events, int(data.get("invalid", 0)))
    except (OSError, ValueError, KeyError, TypeError):
        return Catalog(game)


class Favorites:
    def __init__(self, path: Path):
        self.path = path
        try:
            self._keys = set(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            self._keys = set()

    @staticmethod
    def _id(event: Event) -> str:
        return f"{event.game}:{event.key}"

    def contains(self, event: Event) -> bool:
        return self._id(event) in self._keys

    def toggle(self, event: Event) -> bool:
        ident = self._id(event)
        if ident in self._keys:
            self._keys.discard(ident)
        else:
            self._keys.add(ident)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(sorted(self._keys), ensure_ascii=False), encoding="utf-8")
        return ident in self._keys


GROUP_NAMES = {"item": "Itens", "extra": "Presentes do pokeldn", "pokemon:0": "Outros"}


@dataclass(frozen=True)
class Group:
    key: str                    # "pokemon:893" | "item" | "extra"
    name: str
    species: int
    events: tuple[Event, ...]
    highlights: tuple[str, ...]


def group_events(events: list[Event], species_name: Callable[[int], str]) -> list[Group]:
    buckets: dict[str, list[Event]] = {}
    for event in sorted(events, key=lambda e: e.sort_key):
        key = f"pokemon:{event.species}" if event.kind == "pokemon" else event.kind
        buckets.setdefault(key, []).append(event)
    groups = []
    for key, members in buckets.items():
        species = members[0].species if key.startswith("pokemon:") else 0
        name = species_name(species) if species else GROUP_NAMES.get(key, key)
        seen: list[str] = []
        for event in members:
            seen += [h for h in event.highlights if h not in seen]
        groups.append(Group(key, name, species, tuple(members), tuple(seen[:3])))
    return sorted(groups, key=lambda g: (g.species == 0, g.key == "extra", normalize(g.name)))


def search_groups(groups: list[Group], text: str) -> list[Group]:
    words = normalize(text).split()
    if not words:
        return groups
    return [g for g in groups
            if all(w in normalize(g.name) or any(w in e.search_text for e in g.events) for w in words)]
