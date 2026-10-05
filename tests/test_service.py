from types import SimpleNamespace as NS

import pytest

from distrib import radio, update
from distrib.catalog import Catalog, Event, save_index
from distrib.distributor import Status
from distrib.service import Service

KEYS = "".join(f"key_{i:02d} = {'ab' * 16}\n" for i in range(12))


def ev(key, species):
    return Event(game="swsh", key=key, name=key, kind="pokemon", details=(), files=(key,),
                 sort_key=key, species=species)


class FakeDistributor:
    def __init__(self):
        self.calls, self._status = [], Status(state="starting")

    def start(self):
        self.calls.append("start")

    def stop(self):
        self.calls.append("stop")

    def pause(self):
        self.calls.append("pause")

    def resume(self):
        self.calls.append("resume")

    def status(self):
        return self._status


def make(cfg, boards=(("COM5", 0x1A86, 0x55D4),), hello=None, **kw):
    state = {"boards": list(boards), "hello": 0}

    def comports():
        return [NS(device=d, vid=v, pid=p) for d, v, p in state["boards"]]

    def fake_hello(port):
        state["hello"] += 1
        if hello:
            return hello(port)
        return "ESP32 pokeldn radio"

    for game in ("swsh", "frlg"):
        save_index(Catalog(game, [ev(f"{game}-a", 25), ev(f"{game}-b", 893)]),
                   cfg.catalog_dir / game / "index.json")
    fakes = []

    def make_distributor(game, event):
        fakes.append(FakeDistributor())
        return fakes[-1]

    svc = Service(cfg, comports=comports, hello=fake_hello, make_distributor=make_distributor, **kw)
    return svc, state, fakes


def ready(svc, cfg):
    cfg.keys.parent.mkdir(parents=True, exist_ok=True)
    cfg.keys.write_text(KEYS, encoding="utf-8")
    svc.set_keys(cfg.keys)
    svc.check_board()


def test_initial_snapshot_and_subscribe(cfg):
    svc, _, _ = make(cfg)
    seen = []
    svc.subscribe(seen.append)
    assert seen[0].catalog_ok and not seen[0].keys_ok and not seen[0].ready
    svc.check_board()
    assert seen[-1].board.kind == "ready" and seen[-1].board.port == "COM5"


def test_set_keys_rejects_binary_and_keeps_the_old_file(cfg, tmp_path):
    svc, _, _ = make(cfg)
    good = tmp_path / "prod.keys"
    good.write_text(KEYS, encoding="utf-8")
    svc.set_keys(good)
    assert cfg.keys.read_text(encoding="utf-8") == KEYS and svc.snapshot().keys_ok
    bad = tmp_path / "lixo.keys"
    bad.write_bytes(b"\x00\xff" * 500)
    with pytest.raises(ValueError, match="prod.keys"):
        svc.set_keys(bad)
    assert cfg.keys.read_text(encoding="utf-8") == KEYS


def test_board_states(cfg):
    svc, state, _ = make(cfg, boards=())
    svc.check_board()
    assert svc.snapshot().board.kind == "none"
    state["boards"] = [("COM5", 0x1A86, 0x55D4), ("COM7", 0x10C4, 0xEA60)]
    svc.check_board()
    assert svc.snapshot().board.kind == "many"


def test_board_busy_and_silent(cfg):
    def busy(port):
        raise radio.RadioError("HELLO falhou em COM5: PermissionError: Access is denied")

    svc, _, _ = make(cfg, hello=busy)
    svc.check_board()
    assert svc.snapshot().board.kind == "busy"

    def silent(port):
        raise radio.RadioError("a placa em COM5 não respondeu em 75 s")

    svc, _, _ = make(cfg, hello=silent)
    svc.check_board()
    assert svc.snapshot().board.kind == "silent"


def test_board_port_change_triggers_new_hello(cfg):
    svc, state, _ = make(cfg)
    svc.check_board()
    svc.check_board()
    assert state["hello"] == 1
    state["boards"] = [("COM8", 0x1A86, 0x55D4)]
    svc.check_board()
    assert state["hello"] == 2 and svc.snapshot().board.port == "COM8"
    svc.check_board(force=True)
    assert state["hello"] == 3


def test_groups_and_search(cfg):
    svc, _, _ = make(cfg)
    assert [g.name for g in svc.groups("swsh")] == ["Pikachu", "Zarude"]
    assert [g.name for g in svc.groups("swsh", "zaru")] == ["Zarude"]
    assert svc.event_count("frlg") == 2


def test_start_requires_ready_then_runs(cfg):
    svc, _, fakes = make(cfg)
    event = svc.groups("swsh")[0].events[0]
    with pytest.raises(RuntimeError):
        svc.start("swsh", event)
    ready(svc, cfg)
    svc.start("swsh", event)
    assert fakes[0].calls == ["start"]
    assert svc.snapshot().run.event == event
    fakes[0]._status = Status(state="on_air", since=1.0, channel=6)
    svc._sync_run()
    assert svc.snapshot().run.state == "on_air" and svc.snapshot().run.channel == 6
    svc.pause()
    svc.resume()
    svc.stop()
    assert fakes[0].calls == ["start", "pause", "resume", "stop"]
    assert svc.snapshot().run is None


def test_lost_board_during_run(cfg):
    svc, _, fakes = make(cfg)
    ready(svc, cfg)
    svc.start("swsh", svc.groups("swsh")[0].events[0])
    fakes[0]._status = Status(state="no_board")
    svc._sync_run()
    svc.check_board()
    assert svc.snapshot().board.kind == "none"
    assert "continua" in svc.snapshot().board.message


def test_shutdown_stops_the_distribution(cfg):
    svc, _, fakes = make(cfg)
    ready(svc, cfg)
    svc.start("swsh", svc.groups("swsh")[0].events[0])
    svc.shutdown()
    assert fakes[0].calls[-1] == "stop"


def test_flash_refused_during_run(cfg):
    svc, _, _ = make(cfg)
    ready(svc, cfg)
    svc.start("swsh", svc.groups("swsh")[0].events[0])
    with pytest.raises(RuntimeError):
        svc.flash_board()


def test_check_update_downloads_and_apply_needs_exe(cfg, tmp_path):
    rel = update.Release("v9.0.0", (9, 0, 0), "u", 1, "x")
    got = tmp_path / "novo.exe"
    got.write_bytes(b"n")
    svc, _, _ = make(cfg, latest=lambda: rel, download=lambda r, folder: got)
    svc.check_update()
    assert svc.snapshot().update_state == "ready" and svc.snapshot().update_version == "v9.0.0"
    assert svc.apply_update() is False          # sem exe_path (desenvolvimento)


def test_apply_update_error_is_reported(cfg, tmp_path, monkeypatch):
    rel = update.Release("v9.0.0", (9, 0, 0), "u", 1, "x")
    got = tmp_path / "novo.exe"
    got.write_bytes(b"n")
    exe = tmp_path / "Distribuidor.exe"
    exe.write_bytes(b"v")
    svc, _, _ = make(cfg, latest=lambda: rel, download=lambda r, folder: got, exe_path=exe)
    svc.check_update()

    def boom(new, current):
        raise PermissionError("sem permissão")

    monkeypatch.setattr(update, "apply", boom)
    assert svc.apply_update() is False
    assert svc.snapshot().update_state == "error"


def test_no_update_when_offline(cfg):
    def offline():
        raise OSError("offline")

    svc, _, _ = make(cfg, latest=offline)
    svc.check_update()
    assert svc.snapshot().update_state == "none"


def test_tela_ligada_so_durante_a_distribuicao(cfg):
    calls = []
    svc, _, _ = make(cfg, keep_screen_on=calls.append)
    ready(svc, cfg)
    svc.start("swsh", svc.groups("swsh")[0].events[0])
    assert calls[-1] is True
    svc.stop()
    assert calls[-1] is False
