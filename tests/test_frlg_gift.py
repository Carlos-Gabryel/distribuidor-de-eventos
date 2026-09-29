import pytest

from distrib import frlg_gift
from distrib.runners import frlg_session

G3 = "Released/Gen 3/ENG"
LUGIA = f"{G3}/10th Anniversary Celebration/Top 10 Distribution/RSEFL - 10ANNIV Lugia (ENG).pk3"
EGG = f"{G3}/WISH Eggs/FL - Wish Drowzee Egg (199B613A).pk3"


def test_build_gift_carries_the_whole_mon(gallery):
    from pokeldn.frlg.rom import mystery_event
    gift = frlg_gift.build_gift(gallery / LUGIA)
    assert gift.slug == "distrib-828027a9"
    assert gift.card.icon_species == 249
    assert gift.card.default_flag_id == frlg_gift.FLAG_ID
    assert mystery_event.describe(gift.mevent).startswith("givepokemon")


def test_register_validates_and_is_idempotent(gallery):
    from pokeldn.frlg.gift.gift_registry import GIFT_REGISTRY
    slug = frlg_gift.register(gallery / LUGIA)
    assert slug in GIFT_REGISTRY.live_choices
    assert frlg_gift.register(gallery / LUGIA) == slug


def test_egg_is_refused(gallery):
    with pytest.raises(frlg_gift.GiftError, match="ovo"):
        frlg_gift.load_mon(gallery / EGG)


def test_garbage_is_refused(tmp_path):
    bad = tmp_path / "lixo.pk3"
    bad.write_bytes(bytes(range(80)))
    with pytest.raises(frlg_gift.GiftError):
        frlg_gift.load_mon(bad)


def test_describe(gallery):
    assert frlg_gift.describe(gallery / LUGIA) == "LUGIA Nv70 OT 10ANNIV PID 828027a9"


def test_runner_registers_before_the_host_parser(gallery, capsys):
    from distrib import config
    with pytest.raises(SystemExit) as exc:
        frlg_session.main(["--pokeldn", str(config.load().pokeldn_dir),
                           "--pk3", str(gallery / LUGIA), "--help"])
    assert exc.value.code == 0
    assert "distrib-828027a9" in capsys.readouterr().out
