"""Gera dist/Distribuidor.exe (Windows) ou dist/Distribuidor-x86_64.AppImage (Linux) com o flet pack
(PyInstaller): app + pokeldn v0.5.0 + PKHeX + firmwares."""
import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request
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
LINUX = sys.platform.startswith("linux")
PKHEX_EXE = "pokeldn-pkhex" if LINUX else "pokeldn-pkhex.exe"
APPIMAGE = ROOT / "dist" / "Distribuidor-x86_64.AppImage"
# appimagetool fixo numa versão com tag (não o "continuous"), em cache em build/.cache (ignorado pelo git)
TOOL_VERSION = "1.9.1"
TOOL_SHA256 = "ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"
TOOL_URL = f"https://github.com/AppImage/appimagetool/releases/download/{TOOL_VERSION}/appimagetool-x86_64.AppImage"
CACHE = ROOT / "build" / ".cache"


def publish_pkhex() -> None:
    """Compila o serviço .NET do PKHeX (autônomo: quem usa o app não precisa de .NET)."""
    code = subprocess.run(["dotnet", "publish", str(PKHEX), "-c", "Release", "-r", "linux-x64" if LINUX else "win-x64",
                           "-o", str(PKHEX / "dist"), "-warnaserror"], cwd=ROOT).returncode
    if code != 0 or not (PKHEX / "dist" / PKHEX_EXE).is_file():
        raise SystemExit("dotnet publish do PKHeX falhou")


def appimagetool() -> Path:
    tool = CACHE / f"appimagetool-{TOOL_VERSION}-x86_64.AppImage"
    if not tool.is_file():
        CACHE.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(urllib.request.Request(TOOL_URL, headers={"User-Agent": "Distribuidor-build"}),
                                    timeout=120) as resp:
            data = resp.read()
        if hashlib.sha256(data).hexdigest() != TOOL_SHA256:
            raise SystemExit("O appimagetool baixado não confere com o SHA-256 esperado")
        tool.write_bytes(data)
    tool.chmod(0o755)
    return tool


def build_appimage(binary: Path) -> None:
    """AppDir (AppRun -> binário onefile, .desktop, ícone) empacotado pelo appimagetool."""
    appdir = WORK / "Distribuidor.AppDir"
    shutil.rmtree(appdir, ignore_errors=True)
    appdir.mkdir(parents=True)
    shutil.copy2(binary, appdir / "Distribuidor")
    shutil.copy2(ROOT / "ui" / "assets" / "icon.png", appdir / "distribuidor.png")
    (appdir / "distribuidor.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Distribuidor de Eventos\nExec=Distribuidor\n"
        "Icon=distribuidor\nCategories=Utility;\nTerminal=false\n", encoding="utf-8")
    apprun = appdir / "AppRun"
    apprun.write_text('#!/bin/sh\nexec "$(dirname "$(readlink -f "$0")")/Distribuidor" "$@"\n', encoding="utf-8")
    apprun.chmod(0o755)
    APPIMAGE.unlink(missing_ok=True)
    # --appimage-extract-and-run: contêiner/CI sem FUSE
    code = subprocess.run([str(appimagetool()), "--appimage-extract-and-run", str(appdir), str(APPIMAGE)],
                          env={**os.environ, "ARCH": "x86_64"}).returncode
    if code != 0 or not APPIMAGE.is_file():
        raise SystemExit("O appimagetool não gerou dist/Distribuidor-x86_64.AppImage")


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
    build_args = ([] if LINUX else ["--console", "--hide-console=hide-early"]) + [
                  f"--paths={ROOT}", f"--paths={POKELDN}", f"--paths={POKELDN / 'bin'}",
                  f"--paths={POKELDN / 'vendor' / 'LDN'}",
                  "--hidden-import=swsh_gift_host", "--hidden-import=frlg_mg_host",
                  "--collect-submodules=pokeldn", "--collect-submodules=ldn",
                  "--collect-submodules=distrib", "--collect-submodules=ui",
                  "--collect-all=esptool", "--collect-all=esp_pylib",
                  "--exclude-module=pytest", "--exclude-module=textual"]
    icon = ROOT / "ui" / "assets" / ("icon.png" if LINUX else "icon.ico")
    args = [sys.executable, "-c", FLET, "pack", str(ROOT / "main.py"), "--name", "Distribuidor", "-y",
            "--distpath", str(ROOT / "dist"), "--icon", str(icon),
            *([] if LINUX else ["--product-name", "Distribuidor de Eventos", "--product-version", __version__,
                                "--file-version", f"{__version__}.0"]),
            "--add-data",
            *[f"{src}{os.pathsep}{dest}" for src, dest in data],
            *[f"--pyinstaller-build-args={arg}" for arg in build_args]]
    WORK.mkdir(exist_ok=True)
    # o flet pack roda em .pack/ (o -y apaga ./build); o collect-submodules precisa achar os pacotes
    paths = [ROOT, POKELDN, POKELDN / "bin", POKELDN / "vendor" / "LDN"]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(map(str, paths))}
    code = subprocess.run(args, cwd=WORK, env=env).returncode
    exe = ROOT / "dist" / ("Distribuidor" if LINUX else "Distribuidor.exe")
    if code == 0 and not exe.exists():
        raise SystemExit(f"O flet pack terminou sem gerar dist/{exe.name}")
    if code == 0 and LINUX:
        build_appimage(exe)
    return code


if __name__ == "__main__":
    sys.exit(main())
