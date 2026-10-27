"""Atualização automática pelo GitHub Releases: achar, baixar (conferindo o SHA-256) e trocar o .exe.

O Windows não deixa sobrescrever um .exe aberto, mas deixa renomeá-lo: o atual vira
Distribuidor.exe.old, o novo assume o nome e é aberto; a próxima abertura apaga o .old.

No Linux o app roda como AppImage ($APPIMAGE): o novo arquivo é baixado ao lado do atual e o
substitui com os.replace (o Linux deixa trocar um arquivo em uso). Fora de um AppImage (rodando
do código-fonte) só avisa que há versão nova.
"""
from __future__ import annotations

import hashlib
import json
import re
import os
import shutil
import sys
import subprocess
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from distrib.platform import IS_ANDROID

REPO = "Carlos-Gabryel/distribuidor-de-eventos"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
IS_LINUX = sys.platform.startswith("linux") and not IS_ANDROID


def asset_name() -> str:
    """O arquivo do Release que este app instala: .apk no Android, AppImage no Linux, .exe no Windows."""
    if IS_ANDROID:
        return "Distribuidor.apk"
    return "Distribuidor-x86_64.AppImage" if IS_LINUX else "Distribuidor.exe"


def appimage() -> Path | None:
    """O AppImage em execução (None fora de um: Windows, Android ou código-fonte no Linux)."""
    path = os.environ.get("APPIMAGE") if IS_LINUX else None
    return Path(path) if path else None


def notify_only() -> bool:
    """True quando o app só avisa da versão nova, sem baixar: Android e Linux fora de um AppImage."""
    return IS_ANDROID or (IS_LINUX and appimage() is None)


def download_dir(data_dir: Path) -> Path:
    """Onde baixar: ao lado do AppImage (o os.replace precisa do mesmo volume), senão em dados/updates."""
    return appimage().parent if appimage() is not None else data_dir / "updates"


HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "Distribuidor"}


class UpdateError(Exception):
    pass


@dataclass(frozen=True)
class Release:
    tag: str
    version: tuple[int, ...]
    url: str
    size: int
    sha256: str
    html_url: str = field(default="", compare=False)   # página do Release (Android abre no navegador)


def parse_version(text: str) -> tuple[int, ...]:
    match = re.fullmatch(r"v?(\d+(?:\.\d+)*)", text.strip())
    if not match:
        raise UpdateError(f"versão inválida: {text!r}")
    return tuple(int(part) for part in match.group(1).split("."))


def _release(opener) -> dict:
    with opener(urllib.request.Request(API, headers=HEADERS), timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def latest(opener=urllib.request.urlopen) -> Release | None:
    data = _release(opener)
    for asset in data.get("assets", []):
        if asset.get("name") != asset_name():
            continue
        digest = asset.get("digest") or ""
        if not digest.startswith("sha256:") and not notify_only():     # quem só avisa não baixa
            raise UpdateError("o Release não publica o SHA-256 do arquivo")
        return Release(data["tag_name"], parse_version(data["tag_name"]),
                       asset["browser_download_url"], int(asset["size"]),
                       digest.removeprefix("sha256:"), data.get("html_url", ""))
    return None


def find_asset(name: str, opener=urllib.request.urlopen) -> str | None:
    """URL de download de um arquivo do Release mais recente (None se ele não existir)."""
    for asset in _release(opener).get("assets", []):
        if asset.get("name") == name:
            return asset["browser_download_url"]
    return None


def newer(release: Release | None, current: str) -> bool:
    return release is not None and release.version > parse_version(current)


def download(release: Release, folder: Path, opener=urllib.request.urlopen) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    part = folder / (asset_name() + ".part")
    digest, size = hashlib.sha256(), 0
    request = urllib.request.Request(release.url, headers={"User-Agent": "Distribuidor"})
    with opener(request, timeout=60) as resp, open(part, "wb") as out:
        while chunk := resp.read(1 << 16):
            digest.update(chunk)
            out.write(chunk)
            size += len(chunk)
    if size != release.size or digest.hexdigest() != release.sha256.lower():
        part.unlink(missing_ok=True)
        raise UpdateError("o download não confere (tamanho ou SHA-256)")
    ready = folder / f"Distribuidor-{release.tag}{'.AppImage' if IS_LINUX else '.exe'}"
    part.replace(ready)
    return ready


def apply(new_exe: Path, exe: Path, launch=subprocess.Popen) -> None:
    if IS_LINUX:
        new_exe.chmod(0o755)
        os.replace(new_exe, exe)        # atômico no mesmo volume; o AppImage aberto continua válido
        launch([str(exe)], close_fds=True)
        return
    old = exe.with_name(exe.name + ".old")
    old.unlink(missing_ok=True)
    exe.rename(old)
    try:
        shutil.move(str(new_exe), str(exe))
    except OSError:
        old.rename(exe)
        raise
    launch([str(exe)], close_fds=True)


def cleanup(exe: Path) -> None:
    try:
        exe.with_name(exe.name + ".old").unlink(missing_ok=True)
    except OSError:
        pass        # a versão anterior ainda está fechando; fica para a próxima abertura
