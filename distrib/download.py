"""Baixa o Events Gallery (tar.gz do GitHub, uma requisição) e remonta os catálogos."""
from __future__ import annotations

import json
import shutil
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from distrib import update, validated_index
from distrib.catalog import Catalog
from distrib.config import Config
from distrib.platform import IS_ANDROID

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


def fetch_validated(cfg: Config, opener=urllib.request.urlopen, log=print) -> bool:
    """Android: baixa o swsh_validated.json do Release mais recente para `cfg.data_dir`.
    Se falhar, o app segue com o que já tem (o baixado antes ou o embutido)."""
    try:
        url = update.find_asset(validated_index.NOME, opener)
        if url is None:
            log("O Release não traz o catálogo validado; usando o embutido.")
            return False
        with opener(urllib.request.Request(url, headers={"User-Agent": "Distribuidor"}), timeout=60) as resp:
            body = resp.read()
        if "records" not in json.loads(body.decode("utf-8")):
            raise ValueError("sem 'records'")
    except (OSError, ValueError, update.UpdateError) as exc:
        log(f"Não deu para baixar o catálogo validado ({exc}); mantendo o atual.")
        return False
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    target = cfg.data_dir / validated_index.NOME
    tmp = target.with_suffix(".part")
    tmp.write_bytes(body)
    tmp.replace(target)
    log("Catálogo validado pelo PKHeX atualizado.")
    return True


def update_catalogs(cfg: Config, games: tuple[str, ...], opener=urllib.request.urlopen,
                    log=print) -> dict[str, Catalog]:
    from distrib.games import ADAPTERS
    raw = cfg.catalog_dir / "_raw"
    shutil.rmtree(raw, ignore_errors=True)
    log("Baixando o Events Gallery (~56 MB)…")
    with opener(GALLERY_URL, timeout=600) as stream:
        n = extract_gallery(stream, raw, tuple(RAW_PREFIX[g] for g in games))
    log(f"{n} arquivos extraídos.")
    if IS_ANDROID and "swsh" in games:
        fetch_validated(cfg, opener, log)
    catalogs = {}
    for game in games:
        shutil.rmtree(cfg.catalog_dir / game, ignore_errors=True)
        catalog = ADAPTERS[game].build_catalog(raw / RAW_PREFIX[game], cfg)
        log(f"{ADAPTERS[game].title}: {len(catalog.events)} eventos, {catalog.invalid} inválidos.")
        catalogs[game] = catalog
    shutil.rmtree(raw, ignore_errors=True)
    return catalogs
