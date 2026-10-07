"""Deixa o pacote do pokeldn e o LDN que ele traz em vendor/ importáveis."""
import os
import sys
from pathlib import Path


def ensure_importable(pokeldn_dir: Path) -> None:
    for path in (pokeldn_dir / "vendor" / "LDN", pokeldn_dir):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
    # No .exe o ROOT do pokeldn é o _MEIPASS, não vendor/pokeldn: aponta o PKHeX empacotado.
    pkhex = pokeldn_dir / "services" / "pkhex" / "dist" / "pokeldn-pkhex.exe"
    if sys.platform == "win32" and pkhex.is_file():
        os.environ.setdefault("POKELDN_PKHEX", str(pkhex))
