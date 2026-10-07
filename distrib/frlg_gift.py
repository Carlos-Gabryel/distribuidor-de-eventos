"""O presente do FRLG que entrega um .pk3 inteiro, byte a byte, pelo `givepokemon` do Mystery Event.

O console copia a struct Pokemon (100 bytes, criptografada) para a equipe e marca a Pokédex;
o Pokémon chega com o OT, o ID e o PID do arquivo. Equipe cheia -> status 3, nada é escrito.
"""
from __future__ import annotations

from pathlib import Path

from pokeldn.frlg.gift.gift_composer import (
    DeliveryPlan, DeliveryStage, GiftSpec, Message, WonderCardSpec, WonderGift)
from pokeldn.frlg.gift.gift_registry import GIFT_REGISTRY
from pokeldn.frlg.rom import mystery_event
from pokeldn.frlg.save import basestats, mevent_pokemon
from pokeldn.frlg.save.mon import Mon

FLAG_ID = 1010
_IS_EGG = 0x04      # BoxPokemon byte 0x13: isBadEgg:1, hasSpecies:1, isEgg:1 [decomp:include/pokemon.h]


class GiftError(Exception):
    """Um .pk3 que não pode ser entregue."""


def is_egg(mon: Mon) -> bool:
    return bool(mon.raw[19] & _IS_EGG)


def load_mon(path: Path) -> Mon:
    try:
        mon = Mon.from_file(path)
    except ValueError as exc:
        raise GiftError(f"{path.name}: {exc}") from exc
    decoded = mon.decode()
    if not decoded or not decoded["checksum_ok"]:
        raise GiftError(f"{path.name}: checksum inválido")
    if decoded["species"] not in basestats.BASE_STATS:
        raise GiftError(f"{path.name}: espécie {decoded['species']} desconhecida")
    if is_egg(mon):
        raise GiftError(f"{path.name}: é um ovo (fora da v1)")
    return mon


def describe(path: Path) -> str:
    d = load_mon(path).decode()
    return f"{d['nickname']} Nv{d['level']} OT {d['otName']} PID {d['pid']:08x}"


def build_gift(path: Path) -> WonderGift:
    mon = load_mon(path)
    script = mystery_event.MysteryEventScript()
    script.givepokemon(script.blob(mevent_pokemon.build_givepokemon_payload(mon))).end()
    return WonderGift(
        slug=f"distrib-{mon.pid:08x}",
        card=WonderCardSpec(
            icon_species=mon.species,
            title="MYSTERY EVENT",
            subtitle="A GIFT FROM THE PAST",
            body=("A special POKEMON from a past",
                  "event was sent straight to your",
                  "party."),
            footer1="Distribuidor",
            default_flag_id=FLAG_ID),
        intro_message="Thank you for using the MYSTERY\nGIFT System.",
        event=GiftSpec(repeatable=True),
        delivery=DeliveryPlan(delivery=(
            DeliveryStage(Message("The POKEMON was sent straight to\nyour party, {PLAYER}.")),
        )),
        completed_message="The POKEMON went straight to your\nparty.",
        mevent=script.assemble(),
    )


def register(path: Path) -> str:
    gift = build_gift(path)
    if gift.slug not in GIFT_REGISTRY.live_choices:
        GIFT_REGISTRY.register_definition(gift)     # valida e compila; ValueError se algo não cabe
    return gift.slug
