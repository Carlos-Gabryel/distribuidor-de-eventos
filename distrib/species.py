"""Nomes das espécies e a conversão do índice interno da Gen 3 para o número nacional."""
from __future__ import annotations

from functools import lru_cache

from distrib.species_data import SPECIES


def name(national: int) -> str:
    entry = SPECIES.get(national)
    return entry[1] if entry else f"#{national}"


@lru_cache(maxsize=1)
def _by_identifier() -> dict[str, int]:
    return {ident: n for n, (ident, _) in SPECIES.items()}


def gen3_to_national(internal: int) -> int:
    """0 quando o índice não é de uma espécie (vazio, ou os Unown 'OLD_' do cartucho)."""
    from pokeldn.frlg.save.species_names import SPECIES as GEN3
    gen3 = GEN3.get(internal, "")
    if not gen3 or gen3 == "NONE" or gen3.startswith("OLD_"):
        return 0
    return _by_identifier().get(gen3.lower().replace("_", "-"), 0)
