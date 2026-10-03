"""Gera ui/assets/icon.ico (Poké Ball) para o .exe."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "ui" / "assets" / "icon.ico"


def main() -> None:
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    box = (8, 8, size - 8, size - 8)
    d.ellipse(box, fill="#F4F5F7")
    d.pieslice(box, 180, 360, fill="#E8445A")
    d.rectangle((8, size // 2 - 10, size - 8, size // 2 + 10), fill="#0E0F12")
    r = 40
    c = size // 2
    d.ellipse((c - r, c - r, c + r, c + r), fill="#0E0F12")
    d.ellipse((c - r + 16, c - r + 16, c + r - 16, c + r - 16), fill="#F4F5F7")
    img.save(OUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(OUT)


if __name__ == "__main__":
    main()
