"""Baixa o Events Gallery (tar.gz do GitHub, uma requisição) e remonta os catálogos."""
from __future__ import annotations

import shutil
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from distrib.catalog import Catalog
from distrib.config import Config

GALLERY_URL = "https://codeload.github.com/projectpokemon/EventsGallery/tar.gz/refs/heads/master"
RAW_PREFIX = {"swsh": "Released/Gen 8/SwSh/Wondercards", "frlg": "Released/Gen 3"}


def extract_gallery(stream: BinaryIO, dest: Path, prefixes: tuple[str, ...]) -> int:
    count = 0
    with tarfile.open(fileobj=stream, mode="r|gz") as tar:
        for member in tar:
            if not member.isfile():
                continue
            parts = PurePosixPath(member.name).parts[1:]       # tira "EventsGallery-master/"
            if ".." in parts or not parts:
                continue
            rel = PurePosixPath(*parts)
            if not any(rel.as_posix().startswith(p + "/") for p in prefixes):
                continue
            if rel.suffix.lower() not in (".wc8", ".pk3"):
                continue
            target = dest.joinpath(*rel.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            count += 1
    return count


def update_catalogs(cfg: Config, games: tuple[str, ...], opener=urllib.request.urlopen,
                    log=print) -> dict[str, Catalog]:
    from distrib.games import ADAPTERS
    raw = cfg.catalog_dir / "_raw"
    shutil.rmtree(raw, ignore_errors=True)
    log("Baixando o Events Gallery (~56 MB)…")
    with opener(GALLERY_URL, timeout=600) as stream:
        n = extract_gallery(stream, raw, tuple(RAW_PREFIX[g] for g in games))
    log(f"{n} arquivos extraídos.")
    catalogs = {}
    for game in games:
        shutil.rmtree(cfg.catalog_dir / game, ignore_errors=True)
        catalog = ADAPTERS[game].build_catalog(raw / RAW_PREFIX[game], cfg)
        log(f"{ADAPTERS[game].title}: {len(catalog.events)} eventos, {catalog.invalid} inválidos.")
        catalogs[game] = catalog
    shutil.rmtree(raw, ignore_errors=True)
    return catalogs
