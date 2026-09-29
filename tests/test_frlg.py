from pathlib import Path

from distrib.games import frlg
from distrib.games.base import Update


def adapter(cfg):
    return frlg.FrlgAdapter(cfg.state_dir / "rodizio_pid.json")


def test_event_name_strips_prefix_and_pid_tag():
    assert frlg.event_name(Path("RSEFL - WISHMKR Jirachi (1910) (ENG).pk3")) \
        == "WISHMKR Jirachi (ENG)"
    assert frlg.event_name(Path("FL - Wish Drowzee Egg (199B613A).pk3")) == "Wish Drowzee Egg"
    assert frlg.event_name(Path("RSEFL - 10ANNIV Lugia (ENG).pk3")) == "10ANNIV Lugia (ENG)"


def test_catalog_groups_pid_variants_and_skips_eggs(gallery, cfg):
    cat = adapter(cfg).build_catalog(gallery / frlg.FRLG_RAW, cfg)
    pokemon = {e.name: e for e in cat.events if e.kind == "pokemon"}
    assert set(pokemon) == {"WISHMKR Jirachi (ENG)", "10ANNIV Lugia (ENG)"}
    assert len(pokemon["WISHMKR Jirachi (ENG)"].files) == 2
    details = dict(pokemon["10ANNIV Lugia (ENG)"].details)
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


def test_rotation_cycles_variants(gallery, cfg):
    a = adapter(cfg)
    cat = a.build_catalog(gallery / frlg.FRLG_RAW, cfg)
    jirachi = cat.search("jirachi")[0]
    firsts = [a.build_job(jirachi, cfg, "/dev/ttyACM0") for _ in range(3)]
    pk3s = [j.argv[j.argv.index("--pk3") + 1] for j in firsts]
    assert pk3s[0] != pk3s[1]
    assert pk3s[0] == pk3s[2]


def test_rotation_persists_across_instances(gallery, cfg):
    a = adapter(cfg)
    jirachi = a.build_catalog(gallery / frlg.FRLG_RAW, cfg).search("jirachi")[0]
    first = a.build_job(jirachi, cfg, "/dev/ttyACM0")
    second = adapter(cfg).build_job(jirachi, cfg, "/dev/ttyACM0")
    assert first.argv[first.argv.index("--pk3") + 1] != second.argv[second.argv.index("--pk3") + 1]


def test_build_job_for_pk3_and_extra(gallery, cfg):
    a = adapter(cfg)
    cat = a.build_catalog(gallery / frlg.FRLG_RAW, cfg)
    job = a.build_job(cat.search("lugia")[0], cfg, "/dev/ttyACM0")
    assert job.argv[:4] == (str(cfg.python), "-u", "-m", "distrib.runners.frlg_session")
    assert job.argv[job.argv.index("--pokeldn") + 1] == str(cfg.pokeldn_dir)
    assert job.argv[job.argv.index("--idle-timeout") + 1] == str(cfg.frlg_idle_timeout)
    assert job.env["POKELDN_RADIO"] == "esp32:/dev/ttyACM0"
    assert job.cwd == str(cfg.project_dir)
    extra = cat.get("extra:altering-cave")
    job = a.build_job(extra, cfg, "/dev/ttyACM0")
    assert job.argv[job.argv.index("--extra") + 1] == "altering-cave"


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
