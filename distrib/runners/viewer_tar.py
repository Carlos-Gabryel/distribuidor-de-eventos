"""Copia o flet-macos.tar.gz (viewer do Flet) de dentro do app empacotado para o caminho dado.

Usado só pelo build/check_macos.py: o .app é onefile, então os dados só existem na extração do
PyInstaller (sys._MEIPASS) enquanto o processo roda."""
import shutil
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    root = Path(getattr(sys, "_MEIPASS", ""))
    tar = root / "flet_desktop" / "app" / "flet-macos.tar.gz"
    if not getattr(sys, "frozen", False) or not tar.is_file():
        print(f"viewer_tar: {tar} não existe", file=sys.stderr)
        return 1
    shutil.copyfile(tar, argv[0])
    print("viewer_tar ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
