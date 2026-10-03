"""Gera dist/Distribuidor.exe com o flet pack (PyInstaller): app + pokeldn v0.5.0 + PKHeX + firmwares."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from distrib import __version__  # noqa: E402
from distrib.board import FIRMWARE  # noqa: E402

POKELDN = ROOT / "vendor" / "pokeldn"
PKHEX = POKELDN / "services" / "pkhex"
FLET = "import sys; from flet_cli.cli import main; sys.argv[0] = 'flet'; main()"
# O flet pack apaga a pasta build/ do diretório atual: roda numa pasta de trabalho própria (ignorada pelo git).
WORK = ROOT / ".pack"


def publish_pkhex() -> None:
    """Compila o serviço .NET do PKHeX (autônomo: quem usa o app não precisa de .NET)."""
    code = subprocess.run(["dotnet", "publish", str(PKHEX), "-c", "Release", "-r", "win-x64",
                           "-o", str(PKHEX / "dist"), "-warnaserror"], cwd=ROOT).returncode
    if code != 0 or not (PKHEX / "dist" / "pokeldn-pkhex.exe").is_file():
        raise SystemExit("dotnet publish do PKHeX falhou")


def main() -> int:
    missing = [n for n in FIRMWARE.values() if not (ROOT / "firmware" / n).is_file()]
    if missing:
        raise SystemExit(f"Faltam firmwares ({', '.join(missing)}): rode build/fetch_firmware.py")
    publish_pkhex()
    data = [(POKELDN / "bin", "vendor/pokeldn/bin"),
            (POKELDN / "pokeldn", "vendor/pokeldn/pokeldn"),
            (POKELDN / "vendor" / "LDN" / "ldn", "vendor/pokeldn/vendor/LDN/ldn"),
            (POKELDN / "config", "vendor/pokeldn/config"),
            (PKHEX / "dist", "vendor/pokeldn/services/pkhex/dist"),
            (POKELDN / "LICENSE", "vendor/pokeldn"),
            (ROOT / "firmware", "firmware"),
            (ROOT / "ui" / "assets", "ui/assets"),
            (ROOT / "LICENSE", ".")]
    build_args = ["--console", "--hide-console=hide-early",
                  f"--paths={ROOT}", f"--paths={POKELDN}", f"--paths={POKELDN / 'bin'}",
                  f"--paths={POKELDN / 'vendor' / 'LDN'}",
                  "--hidden-import=swsh_gift_host", "--hidden-import=frlg_mg_host",
                  "--collect-submodules=pokeldn", "--collect-submodules=ldn",
                  "--collect-submodules=distrib", "--collect-submodules=ui",
                  "--collect-all=esptool", "--collect-all=esp_pylib",
                  "--exclude-module=pytest", "--exclude-module=textual"]
    args = [sys.executable, "-c", FLET, "pack", str(ROOT / "main.py"), "--name", "Distribuidor", "-y",
            "--distpath", str(ROOT / "dist"), "--icon", str(ROOT / "ui" / "assets" / "icon.ico"),
            "--product-name", "Distribuidor de Eventos", "--product-version", __version__,
            "--file-version", f"{__version__}.0", "--add-data",
            *[f"{src}{os.pathsep}{dest}" for src, dest in data],
            *[f"--pyinstaller-build-args={arg}" for arg in build_args]]
    WORK.mkdir(exist_ok=True)
    code = subprocess.run(args, cwd=WORK).returncode
    exe = ROOT / "dist" / "Distribuidor.exe"
    if code == 0 and not exe.exists():
        raise SystemExit("O flet pack terminou sem gerar dist/Distribuidor.exe")
    return code


if __name__ == "__main__":
    sys.exit(main())
