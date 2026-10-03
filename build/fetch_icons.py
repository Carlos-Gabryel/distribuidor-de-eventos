"""Baixa os ícones Lucide usados pela interface (licença ISC) para ui/assets/icons/."""
import urllib.request
from pathlib import Path

VERSION = "1.50.0"
BASE = f"https://unpkg.com/lucide-static@{VERSION}"
NAMES = ("gamepad-2", "cpu", "settings", "search", "play", "pause", "square", "download",
         "key-round", "usb", "refresh-cw", "folder-open", "external-link", "check",
         "triangle-alert", "package", "zap", "minus", "copy", "x")
OUT = Path(__file__).resolve().parent.parent / "ui" / "assets" / "icons"


def get(path: str) -> bytes:
    with urllib.request.urlopen(f"{BASE}/{path}", timeout=30) as resp:
        return resp.read()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        (OUT / f"{name}.svg").write_bytes(get(f"icons/{name}.svg"))
    (OUT / "LICENSE").write_bytes(get("LICENSE"))
    print(f"{len(NAMES)} ícones em {OUT}")


if __name__ == "__main__":
    main()
