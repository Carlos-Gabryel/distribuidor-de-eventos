"""Gera distrib/species_data.py a partir dos CSVs do PokeAPI. Rodar só quando faltar espécie."""
import csv
import io
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/"
OUT = Path(__file__).resolve().parent.parent / "distrib" / "species_data.py"


def fetch(name: str) -> list[dict]:
    with urllib.request.urlopen(BASE + name, timeout=60) as resp:
        return list(csv.DictReader(io.TextIOWrapper(resp, encoding="utf-8")))


def main() -> None:
    english = {int(r["pokemon_species_id"]): r["name"]
               for r in fetch("pokemon_species_names.csv") if r["local_language_id"] == "9"}
    rows = sorted((int(r["id"]), r["identifier"], english[int(r["id"])])
                  for r in fetch("pokemon_species.csv"))
    lines = ['"""Gerado por build/gen_species.py a partir do PokeAPI. Não editar à mão."""', "",
             "# número nacional: (identificador do PokeAPI, nome em inglês)", "SPECIES = {"]
    lines += [f"    {n}: ({ident!r}, {name!r})," for n, ident, name in rows]
    lines += ["}", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(rows)} espécies em {OUT}")


if __name__ == "__main__":
    main()
