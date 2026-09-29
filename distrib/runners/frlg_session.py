"""Host de UMA sessão do Mystery Gift do FireRed/LeafGreen (rodar como root).

    python -m distrib.runners.frlg_session --pokeldn DIR --pk3 ARQ [args do frlg_mg_host]
    python -m distrib.runners.frlg_session --pokeldn DIR --extra altering-cave [args…]

Registra o nosso presente no GIFT_REGISTRY antes de o parser do bin/frlg_mg_host.py ser montado
(as opções de --gift saem do registro) e chama o main() dele com --end-on-success.
Sai com o código do host: 0 entregue, 1 não entregue, 124 sem console, 130 interrompido.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from distrib.pokeldn_path import ensure_importable


def load_host(pokeldn_dir: Path):
    spec = importlib.util.spec_from_file_location(
        "frlg_mg_host", pokeldn_dir / "bin" / "frlg_mg_host.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--pokeldn", required=True, type=Path)
    what = parser.add_mutually_exclusive_group(required=True)
    what.add_argument("--pk3", type=Path)
    what.add_argument("--extra")
    args, host_args = parser.parse_known_args(argv)
    if host_args[:1] == ["--"]:
        host_args = host_args[1:]
    ensure_importable(args.pokeldn)
    if args.pk3 is not None:
        from distrib import frlg_gift
        slug = frlg_gift.register(args.pk3)
        print(f"[distrib] presente {slug}: {frlg_gift.describe(args.pk3)}", flush=True)
    else:
        slug = args.extra
        print(f"[distrib] extra {slug}", flush=True)
    host = load_host(args.pokeldn)
    return host.main(["--live", "--gift", slug, "--end-on-success", *host_args])


if __name__ == "__main__":
    sys.exit(main())
