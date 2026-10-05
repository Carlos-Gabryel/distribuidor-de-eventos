"""Monta o staging de android/app/ e gera dist/Distribuidor.apk com o `flet build apk`.

Só roda de verdade no CI (Linux): o `flet build` no Windows exige symlinks (Modo Desenvolvedor).
Uso: python build/pack_android.py --wheels android/wheels [--stage-only]
Antes: python build/fetch_firmware.py e o wheel do unicorn (android/scripts/build_unicorn_wheel.sh).
"""
import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from distrib.board import FIRMWARE  # noqa: E402

APP = ROOT / "android" / "app"
POKELDN = ROOT / "vendor" / "pokeldn"
ESPTOOL = "5.4.0"
NETLINK = "0.0.15"  # o mesmo do setup.py do vendor/LDN; o host do LDN importa netlink (só depende do trio)
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info")


def copy(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=SKIP)


def embed_sdist(dist: str, version: str, package: str) -> None:
    """Pacotes só com sdist no PyPI (o flet build usa --only-binary): embute o pacote puro no app."""
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, "-m", "pip", "download", f"{dist}=={version}", "--no-deps",
                        "--no-binary", ":all:", "-d", tmp, "-q"], check=True)
        with tarfile.open(next(Path(tmp).glob("*.tar.gz"))) as tar:
            tar.extractall(tmp, filter="data")
        copy(next(Path(tmp).glob(f"*/{package}")), APP / package)


def stage(wheels: Path) -> None:
    missing = [n for n in FIRMWARE.values() if not (ROOT / "firmware" / n).is_file()]
    if missing:
        raise SystemExit(f"Faltam firmwares ({', '.join(missing)}): rode build/fetch_firmware.py")
    if not list(wheels.glob("unicorn-*.whl")):
        raise SystemExit(f"Sem o wheel do unicorn em {wheels}: rode android/scripts/build_unicorn_wheel.sh")
    copy(ROOT / "distrib", APP / "distrib")          # inclui swsh_validated.json (pré-validado pelo PKHeX)
    copy(ROOT / "ui", APP / "ui")
    copy(ROOT / "firmware", APP / "firmware")
    # pokeldn v0.5.0 sem services/pkhex (.NET não roda no celular), no mesmo desenho do .exe
    base = APP / "vendor" / "pokeldn"
    if base.parent.exists():
        shutil.rmtree(base.parent)
    for rel in ("pokeldn", "bin", "config", "vendor/LDN/ldn"):
        copy(POKELDN / rel, base / rel)
    shutil.copy2(POKELDN / "LICENSE", base / "LICENSE")
    shutil.copy2(ROOT / "LICENSE", APP / "LICENSE")
    # o Flet empacota ./assets (e usa assets/icon.png como ícone do app)
    for item in (ROOT / "ui" / "assets").iterdir():
        if item.name != "icon.ico":
            if item.is_dir():
                copy(item, APP / "assets" / item.name)
            else:
                shutil.copy2(item, APP / "assets" / item.name)
    embed_sdist("esptool", ESPTOOL, "esptool")
    embed_sdist("python-netlink", NETLINK, "netlink")
    pyproject = APP / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    pyproject.write_text(text.replace("@WHEELS@", wheels.resolve().as_posix()), encoding="utf-8")


def build() -> None:
    subprocess.run(["flet", "build", "apk", "--yes", "--no-rich-output", "-v"], cwd=APP, check=True,
                   env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    apks = sorted((APP / "build" / "apk").glob("*.apk"))
    if not apks:
        raise SystemExit("O flet build terminou sem gerar o .apk")
    out = ROOT / "dist"
    out.mkdir(exist_ok=True)
    shutil.copy2(apks[0], out / "Distribuidor.apk")
    print(out / "Distribuidor.apk")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheels", type=Path, default=ROOT / "android" / "wheels")
    parser.add_argument("--stage-only", action="store_true")
    args = parser.parse_args()
    stage(args.wheels)
    if not args.stage_only:
        build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
