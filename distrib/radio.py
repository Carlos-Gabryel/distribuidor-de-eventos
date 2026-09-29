"""A placa: achar a porta serial e fazer o HELLO (num processo filho, como os hosts)."""
from __future__ import annotations

import glob
import subprocess
from dataclasses import dataclass

from distrib.catalog import Catalog
from distrib.config import Config

PORT_GLOBS = ("/dev/ttyACM*", "/dev/ttyUSB*")
TITLES = {"swsh": "Sword/Shield", "frlg": "FireRed/LeafGreen"}
_HELLO = (
    "import sys; sys.path[:0] = [sys.argv[2], sys.argv[2] + '/vendor/LDN'];"
    "from pokeldn.ldn import esp32;"
    "r = esp32.Radio.open_serial(sys.argv[1]);"
    "print(r.hello().text); r.close()"
)


class RadioError(Exception):
    pass


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    message: str


def find_port(globber=glob.glob) -> str | None:
    ports = sorted({p for pattern in PORT_GLOBS for p in globber(pattern)})
    return ports[0] if len(ports) == 1 else None


def hello(port: str, cfg: Config, run=subprocess.run) -> str:
    try:
        done = run([str(cfg.python), "-c", _HELLO, port, str(cfg.pokeldn_dir)],
                   capture_output=True, text=True, timeout=20)
    except subprocess.TimeoutExpired as exc:
        raise RadioError(f"a placa em {port} não respondeu em 20 s") from exc
    if done.returncode != 0:
        last = (done.stderr.strip().splitlines() or ["erro desconhecido"])[-1]
        raise RadioError(f"HELLO falhou em {port}: {last}")
    return done.stdout.strip().splitlines()[-1]


def run_checks(cfg: Config, catalogs: dict[str, Catalog], find=find_port,
               hello_fn=hello) -> list[Check]:
    checks = []
    port = find()
    if port is None:
        checks.append(Check("Placa", False, "Plugue a placa (e confira o usbipd attach) e aperte R"))
    else:
        try:
            checks.append(Check("Placa", True, f"{port}, {hello_fn(port, cfg)}"))
        except RadioError as exc:
            checks.append(Check("Placa", False, f"{exc}. Replugue a placa e aperte R"))
    checks.append(Check("prod.keys", cfg.keys.exists(),
                        "encontrado" if cfg.keys.exists()
                        else f"não encontrado em {cfg.keys}; veja docs/instalacao.md"))
    for game, title in TITLES.items():
        catalog = catalogs.get(game) or Catalog(game)
        n = len(catalog.events)
        checks.append(Check(title, n > 0,
                            f"{n} eventos" if n else
                            "catálogo vazio: rode 'python -m distrib atualizar-catalogo'"))
    return checks
