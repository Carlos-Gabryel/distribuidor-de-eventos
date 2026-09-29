"""Deixa o pacote do pokeldn e o LDN que ele traz em vendor/ importáveis."""
import sys
from pathlib import Path


def ensure_importable(pokeldn_dir: Path) -> None:
    for path in (pokeldn_dir / "vendor" / "LDN", pokeldn_dir):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
