"""Baixa do Events Gallery os poucos arquivos reais usados nos testes (rode uma vez)."""
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/projectpokemon/EventsGallery/master/"
FILES = [
    "Released/Gen 8/SwSh/Wondercards/0507 SWSH - Jungle Zarude (Western Release).wc8",
    "Released/Gen 8/SwSh/Wondercards/0106 SWSH - Item Poke Ball x100.wc8",
    "Released/Gen 3/ENG/10th Anniversary Celebration/Top 10 Distribution/RSEFL - 10ANNIV Lugia (ENG).pk3",
    "Released/Gen 3/ENG/WSHMKR Jirachi/RSEFL - WISHMKR Jirachi (1910) (ENG).pk3",
    "Released/Gen 3/ENG/WSHMKR Jirachi/RSEFL - WISHMKR Jirachi (4CB7) (ENG).pk3",
    "Released/Gen 3/ENG/WISH Eggs/FL - Wish Drowzee Egg (199B613A).pk3",
]

if __name__ == "__main__":
    root = Path(__file__).parent / "gallery"
    for rel in FILES:
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = BASE + urllib.parse.quote(rel)
        dest.write_bytes(urllib.request.urlopen(url, timeout=60).read())
        print(dest.stat().st_size, rel)
