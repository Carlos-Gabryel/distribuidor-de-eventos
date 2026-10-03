from pathlib import Path

import pytest

from distrib.games import frlg
from distrib.games.base import Update


def adapter(cfg):
    return frlg.FrlgAdapter(cfg.state_dir / "rodizio_pid.json")


def test_serial_numbered_variants_are_one_event(gallery, cfg, tmp_path):
    import shutil
    raw = tmp_path / "raw" / "ENG" / "Toys R Us" / "MYSTRY Mew"
    raw.mkdir(parents=True)
    src = gallery / frlg.FRLG_RAW / "ENG/WSHMKR Jirachi"
    for i, f in enumerate(sorted(src.glob("*.pk3"))):
        shutil.copyfile(f, raw / f"RSEFL - MYSTRY ({i + 1:03d} of 430) Mew (ENG).pk3")
    cat = adapter(cfg).build_catalog(tmp_path / "raw", cfg)
    pokemon = [e for e in cat.events if e.kind == "pokemon"]
    assert len(pokemon) == 1 and len(pokemon[0].files) == 2


def test_per_person_tids_are_one_event(gallery, cfg, tmp_path):
    raw = tmp_path / "raw" / "ENG" / "PCNY"
    raw.mkdir(parents=True)
    lugia = (gallery / frlg.FRLG_RAW /
             "ENG/10th Anniversary Celebration/Top 10 Distribution/RSEFL - 10ANNIV Lugia (ENG).pk3")
    data = bytearray(lugia.read_bytes())
    for i, tid in enumerate((111, 222)):
        data[4:6] = tid.to_bytes(2, "little")
        (raw / f"PCNYc {i:05d} Lugia (ENG).pk3").write_bytes(bytes(data))
    cat = adapter(cfg).build_catalog(tmp_path / "raw", cfg)
    pokemon = [e for e in cat.events if e.kind == "pokemon"]
    assert len(pokemon) == 1 and len(pokemon[0].files) == 2
    assert dict(pokemon[0].details)["TID"] == "vários (2)"


def test_catalog_groups_pid_variants_and_skips_eggs(gallery, cfg):
    cat = adapter(cfg).build_catalog(gallery / frlg.FRLG_RAW, cfg)
    pokemon = {e.name: e for e in cat.events if e.kind == "pokemon"}
    assert set(pokemon) == {"JIRACHI (WISHMKR, ENG)", "LUGIA (10ANNIV, ENG)"}
    assert len(pokemon["JIRACHI (WISHMKR, ENG)"].files) == 2
    details = dict(pokemon["LUGIA (10ANNIV, ENG)"].details)
    assert details["OT"] == "10ANNIV"
    assert details["Nível"] == "70"
    assert details["Variantes (PID)"] == "1"
    assert details["Pasta"] == "ENG/10th Anniversary Celebration/Top 10 Distribution"
    assert cat.invalid == 1                      # o ovo
    for event in pokemon.values():
        for f in event.files:
            assert (cfg.catalog_dir / "frlg" / f).stat().st_size == 80


def test_catalog_includes_extras(gallery, cfg):
    cat = adapter(cfg).build_catalog(gallery / frlg.FRLG_RAW, cfg)
    extras = [e for e in cat.events if e.kind == "extra"]
    assert {e.key for e in extras} == {f"extra:{slug}" for slug, _, _ in frlg.EXTRAS}
    assert all(e.files == () for e in extras)


def test_extras_exist_in_the_pokeldn_registry():
    from pokeldn.frlg.gift.gift_registry import GIFT_REGISTRY
    assert {slug for slug, _, _ in frlg.EXTRAS} <= set(GIFT_REGISTRY.live_choices)


def pk3_of(job):
    return job.argv[job.argv.index("--pk3") + 1]


def test_rotation_advances_only_on_delivery(gallery, cfg):
    a = adapter(cfg)
    jirachi = a.build_catalog(gallery / frlg.FRLG_RAW, cfg).search("jirachi")[0]
    first = a.build_job(jirachi, cfg, "/dev/ttyACM0")
    again = a.build_job(jirachi, cfg, "/dev/ttyACM0")      # sessão sem entrega
    assert pk3_of(first) == pk3_of(again)
    again.on_delivered()
    second = a.build_job(jirachi, cfg, "/dev/ttyACM0")
    assert pk3_of(second) != pk3_of(first)
    second.on_delivered()
    assert pk3_of(a.build_job(jirachi, cfg, "/dev/ttyACM0")) == pk3_of(first)


def test_rotation_persists_across_instances(gallery, cfg):
    a = adapter(cfg)
    jirachi = a.build_catalog(gallery / frlg.FRLG_RAW, cfg).search("jirachi")[0]
    first = a.build_job(jirachi, cfg, "/dev/ttyACM0")
    first.on_delivered()
    second = adapter(cfg).build_job(jirachi, cfg, "/dev/ttyACM0")
    assert pk3_of(first) != pk3_of(second)


def test_build_job_for_pk3_and_extra(gallery, cfg):
    from distrib import runner
    a = adapter(cfg)
    cat = a.build_catalog(gallery / frlg.FRLG_RAW, cfg)
    job = a.build_job(cat.search("lugia")[0], cfg, "COM5")
    rest = job.argv[len(runner.command()):]
    assert rest[:2] == ("--module", "distrib.runners.frlg_session")
    assert rest[rest.index("--pokeldn") + 1] == str(cfg.pokeldn_dir)
    assert rest[rest.index("--idle-timeout") + 1] == str(cfg.frlg_idle_timeout)
    assert job.env["POKELDN_RADIO"] == "esp32:COM5"
    assert job.cwd == str(cfg.pokeldn_dir)
    extra = cat.get("extra:altering-cave")
    job = a.build_job(extra, cfg, "COM5")
    assert job.argv[job.argv.index("--extra") + 1] == "altering-cave"


def test_catalog_fills_species_and_highlights(gallery, cfg):
    cat = adapter(cfg).build_catalog(gallery / frlg.FRLG_RAW, cfg)
    lugia = cat.search("lugia")[0]
    assert lugia.species == 249
    assert "Nv 70" in lugia.highlights
    assert lugia.region == "ENG"
    assert cat.get("extra:altering-cave").species == 0


FRLG_LOG = Path(__file__).parent / "fixtures" / "logs" / "frlg_v050.txt"


@pytest.mark.skipif(not FRLG_LOG.exists(), reason="log real do FRLG ainda não gravado (Task 2)")
def test_parse_real_v050_log(fixtures):
    a = frlg.FrlgAdapter(None)
    lines = FRLG_LOG.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    states = [u.state for u in map(a.parse_line, lines) if u and u.state]
    assert "on_air" in states and "console" in states and "delivered" in states
    assert "error" not in states


def test_parse_line():
    a = frlg.FrlgAdapter(None)
    assert a.parse_line("[    0.2s] Hosting. Waiting for the console to join "
                        "(ssid=b19e9397..., channel 1).") == Update(state="on_air", channel=1)
    assert a.parse_line("[    0.0s] Advertising ACTIVITY_WONDER_CARD. On the Switch") is None
    assert a.parse_line("[   9.1s] Mystery Event script status: 2 (success)") \
        == Update(state="delivered")
    assert a.parse_line("Mystery Event script status: 3 (incompatible, or givepokemon found "
                        "a full party)") == Update(state="party_full")
    assert a.parse_line("Wonder Card delivered. On the Switch, talk to the delivery man") \
        == Update(state="delivered")
    assert a.parse_line("Session finished without delivering anything: x") \
        == Update(state="not_delivered", detail="Session finished without delivering anything: x")
    assert a.parse_line("[distrib] presente distrib-828027a9: LUGIA Nv70 OT 10ANNIV PID 828027a9") \
        == Update(detail="LUGIA Nv70 OT 10ANNIV PID 828027a9")
    assert a.parse_line("[status] mode=0") is None
    assert a.parse_line("[  870.7s] A console joined the network.") == Update(state="console")
    assert a.parse_line("[  870.7s] Switch joined the Linux LDN host successfully.") is None
