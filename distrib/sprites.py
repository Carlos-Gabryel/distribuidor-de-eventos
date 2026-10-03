"""Sprites dos Pokémon (repositório de sprites do PokeAPI) num cache local. Nunca levanta erro."""
from __future__ import annotations

import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon"
PNG = b"\x89PNG\r\n\x1a\n"
MAX_BYTES = 200_000
OFFLINE_COOLDOWN = 60.0


class SpriteCache:
    def __init__(self, folder: Path, opener=urllib.request.urlopen, clock=time.monotonic):
        self.folder, self.opener, self.clock = folder, opener, clock
        self._offline_until = 0.0
        self._lock = threading.Lock()

    def cached(self, species: int) -> Path | None:
        path = self.folder / f"{species}.png"
        return path if species > 0 and path.exists() else None

    def get(self, species: int) -> Path | None:
        if species <= 0:
            return None
        if (path := self.cached(species)) is not None:
            return path
        missing = self.folder / f"{species}.missing"
        with self._lock:
            if missing.exists() or self.clock() < self._offline_until:
                return None
            try:
                with self.opener(f"{BASE}/{species}.png", timeout=5) as resp:
                    data = resp.read(MAX_BYTES + 1)
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    self.folder.mkdir(parents=True, exist_ok=True)
                    missing.touch()
                return None
            except (OSError, ValueError):
                self._offline_until = self.clock() + OFFLINE_COOLDOWN
                return None
            if not data.startswith(PNG) or len(data) > MAX_BYTES:
                return None
            self.folder.mkdir(parents=True, exist_ok=True)
            tmp = self.folder / f"{species}.tmp"
            tmp.write_bytes(data)
            tmp.replace(self.folder / f"{species}.png")
            return self.folder / f"{species}.png"
