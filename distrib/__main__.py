"""python -m distrib [tui | atualizar-catalogo [swsh|frlg] | checar]"""
from __future__ import annotations

import argparse
import sys

from distrib import config as configmod
from distrib.pokeldn_path import ensure_importable


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m distrib")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("tui", help="abre a interface (padrão)")
    up = sub.add_parser("atualizar-catalogo", help="baixa o Events Gallery e remonta os catálogos")
    up.add_argument("jogos", nargs="*", choices=("swsh", "frlg"))
    sub.add_parser("checar", help="confere placa, prod.keys e catálogos")
    args = parser.parse_args(argv)
    cfg = configmod.load()
    ensure_importable(cfg.pokeldn_dir)

    if args.cmd == "atualizar-catalogo":
        from distrib import download
        download.update_catalogs(cfg, tuple(args.jogos or ("swsh", "frlg")))
        return 0

    from distrib.app import default_services
    services = default_services(cfg)
    if args.cmd == "checar":
        from distrib import radio
        checks = radio.run_checks(cfg, services.catalogs)
        for check in checks:
            print(f"{'✓' if check.ok else '✗'} {check.name}: {check.message}")
        return 0 if all(c.ok for c in checks if c.name in ("Placa", "prod.keys")) else 1

    from distrib.app import DistribApp
    DistribApp(services).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
