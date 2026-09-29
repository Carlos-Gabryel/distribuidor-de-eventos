from distrib.games import swsh
from distrib.games.base import Update

A = swsh.SwshAdapter()


def build(gallery, cfg):
    return A.build_catalog(gallery / swsh.SWSH_RAW, cfg)


def test_catalog_one_event_per_file(gallery, cfg):
    cat = build(gallery, cfg)
    assert {e.name for e in cat.events} == {"Jungle Zarude (Western Release)",
                                            "Item Poke Ball x100"}
    zarude = next(e for e in cat.events if "Zarude" in e.name)
    assert zarude.kind == "pokemon"
    details = dict(zarude.details)
    assert details["Espécie"] == "#893"
    assert details["Nível"] == "60"
    assert details["Shiny"] == "nunca"
    assert details["Jogos"] == "Sword e Shield"
    assert details["Cartão"] == "#0507"
    poke_ball = next(e for e in cat.events if "Poke Ball" in e.name)
    assert poke_ball.kind == "item"


def test_catalog_copies_files_and_writes_index(gallery, cfg):
    cat = build(gallery, cfg)
    base = cfg.catalog_dir / "swsh"
    assert (base / "index.json").exists()
    for event in cat.events:
        assert (base / event.files[0]).stat().st_size == 720


def test_catalog_reseals_and_counts_invalid(gallery, cfg, tmp_path):
    from pokeldn.swsh import wc8
    raw = tmp_path / "raw"
    raw.mkdir()
    good = (gallery / swsh.SWSH_RAW / "0106 SWSH - Item Poke Ball x100.wc8").read_bytes()
    broken = bytearray(good)
    broken[wc8.CHECKSUM_AT] ^= 0xFF
    (raw / "0106 SWSH - Quebrado.wc8").write_bytes(bytes(broken))
    (raw / "0001 SWSH - Curto.wc8").write_bytes(good[:100])
    cat = A.build_catalog(raw, cfg)
    assert [e.name for e in cat.events] == ["Quebrado"]
    assert wc8.sealed((cfg.catalog_dir / "swsh" / cat.events[0].files[0]).read_bytes())
    assert cat.invalid == 1


def test_subfolder_goes_into_the_name(gallery, cfg, tmp_path):
    raw = tmp_path / "raw"
    (raw / "Ranked Battles").mkdir(parents=True)
    src = gallery / swsh.SWSH_RAW / "0106 SWSH - Item Poke Ball x100.wc8"
    (raw / "Ranked Battles" / "0002 SWSH - Doubles S1 Battle Points x50.wc8").write_bytes(
        src.read_bytes())
    cat = A.build_catalog(raw, cfg)
    assert cat.events[0].name == "Ranked Battles: Doubles S1 Battle Points x50"


def test_build_job(gallery, cfg):
    event = build(gallery, cfg).search("zarude")[0]
    job = A.build_job(event, cfg, "/dev/ttyACM0")
    assert job.env["POKELDN_RADIO"] == "esp32:/dev/ttyACM0"
    assert job.argv[0] == str(cfg.python)
    assert job.argv[1:3] == ("-u", str(cfg.pokeldn_dir / "bin" / "swsh_gift_host.py"))
    assert "--no-validate" in job.argv
    record = job.argv[job.argv.index("--record") + 1]
    assert record == str(cfg.catalog_dir / "swsh" / event.files[0])
    assert job.argv[job.argv.index("--keys") + 1] == str(cfg.keys)
    assert job.cwd == str(cfg.pokeldn_dir)


def test_parse_line():
    assert A.parse_line("[host] AP up: ssid=59 ch=11 us=169.254.99.1/x") == Update(channel=11)
    assert A.parse_line("advertising comm id 0x0100abf008968000, scene 0, protocol 1") \
        == Update(state="on_air")
    assert A.parse_line("RuntimeError: LDN host bring-up failed after 3 attempt(s):") \
        == Update(state="error", detail="RuntimeError: LDN host bring-up failed after 3 attempt(s):")
    assert A.parse_line("[status] mode=0 rx_mgmt=1") is None
