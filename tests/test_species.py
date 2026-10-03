from pokeldn.frlg.save.species_names import SPECIES as GEN3

from distrib import species

INTERNAL = {name: n for n, name in GEN3.items()}


def test_name():
    assert species.name(25) == "Pikachu"
    assert species.name(893) == "Zarude"
    assert species.name(99999) == "#99999"


def test_gen3_to_national_known_cases():
    assert species.gen3_to_national(25) == 25
    assert species.gen3_to_national(INTERNAL["TREECKO"]) == 252
    assert species.gen3_to_national(INTERNAL["CHIMECHO"]) == 358
    assert species.gen3_to_national(INTERNAL["NIDORAN_F"]) == 29
    assert species.gen3_to_national(INTERNAL["MR_MIME"]) == 122
    assert species.gen3_to_national(INTERNAL["HO_OH"]) == 250
    assert species.gen3_to_national(INTERNAL["DEOXYS"]) == 386
    assert species.gen3_to_national(0) == 0


def test_gen3_covers_the_whole_hoenn_dex():
    found = {species.gen3_to_national(n) for n, name in GEN3.items()
             if name != "NONE" and not name.startswith("OLD_")}
    assert set(range(1, 387)) <= found
