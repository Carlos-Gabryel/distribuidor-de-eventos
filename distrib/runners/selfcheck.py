"""Smoke test do app congelado, sem placa: python main.py --module distrib.runners.selfcheck

Confere que as dependências nativas, o PKHeX e os firmwares vieram empacotados.
Imprime "selfcheck ok" e sai com 0; se algo faltar, imprime o motivo e sai com 1.
"""
import os
import sys

from distrib.platform import IS_ANDROID


def _problems() -> list[str]:
    problems = []
    try:
        from serial.tools import list_ports
        list_ports.comports()
    except Exception as exc:
        problems.append(f"pyserial: {exc!r}")
    if not getattr(sys, "frozen", False):      # do código-fonte os hosts ficam em pokeldn/bin
        try:
            from distrib.config import load
            sys.path.append(str(load().pokeldn_dir / "bin"))
        except Exception:
            pass
    for name in ("swsh_gift_host", "frlg_mg_host"):
        try:
            __import__(name)
        except Exception as exc:
            problems.append(f"{name}: {exc!r}")
    if not IS_ANDROID:
        pkhex = os.environ.get("POKELDN_PKHEX")
        if not pkhex or not os.access(pkhex, os.X_OK):
            problems.append(f"PKHeX ausente ou não executável (POKELDN_PKHEX={pkhex!r})")
    try:
        from distrib.board import FIRMWARE
        from distrib.config import load
        folder = load().firmware_dir
        problems += [f"firmware ausente: {folder / name}" for name in FIRMWARE.values()
                     if not (folder / name).is_file()]
    except Exception as exc:
        problems.append(f"firmwares: {exc!r}")
    return problems


def main(argv=None) -> int:
    problems = _problems()
    if problems:
        for line in problems:
            print(f"selfcheck falhou: {line}", file=sys.stderr, flush=True)
        return 1
    print("selfcheck ok", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
