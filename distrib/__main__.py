"""python -m distrib atualizar-catalogo [swsh|frlg]  (atalho de desenvolvimento)"""
from __future__ import annotations

import argparse
import sys

from distrib import config as configmod
from distrib.pokeldn_path import ensure_importable


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m distrib")
    sub = parser.add_subparsers(dest="cmd", required=True)
    up = sub.add_parser("atualizar-catalogo", help="baixa o Events Gallery e remonta os catálogos")
    up.add_argument("jogos", nargs="*", choices=("swsh", "frlg"))
    args = parser.parse_args(argv)
    cfg = configmod.load()
    ensure_importable(cfg.pokeldn_dir)
    from distrib import download
    download.update_catalogs(cfg, tuple(args.jogos or ("swsh", "frlg")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
