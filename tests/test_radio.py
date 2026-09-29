import dataclasses
import subprocess

import pytest

from distrib import radio
from distrib.catalog import Catalog, Event


def test_find_port_single_and_ambiguous():
    assert radio.find_port(lambda pattern: ["/dev/ttyACM0"] if "ACM" in pattern else []) \
        == "/dev/ttyACM0"
    assert radio.find_port(lambda pattern: []) is None
    assert radio.find_port(lambda pattern: ["/dev/ttyACM0", "/dev/ttyACM1"]
                           if "ACM" in pattern else []) is None


def test_hello_ok_and_error(cfg):
    ok = lambda *a, **k: subprocess.CompletedProcess(a, 0, "pokeldn-radio esp32 idf=v6.1\n", "")
    assert radio.hello("/dev/ttyACM0", cfg, run=ok) == "pokeldn-radio esp32 idf=v6.1"
    bad = lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "no reply 0x81\n")
    with pytest.raises(radio.RadioError, match="no reply"):
        radio.hello("/dev/ttyACM0", cfg, run=bad)


def test_hello_timeout(cfg):
    def slow(*a, **k):
        raise subprocess.TimeoutExpired(a, 20)
    with pytest.raises(radio.RadioError, match="não respondeu"):
        radio.hello("/dev/ttyACM0", cfg, run=slow)


def test_run_checks(cfg, tmp_path):
    keys = tmp_path / "prod.keys"
    keys.write_text("x")
    cfg = dataclasses.replace(cfg, keys=keys)
    ev = Event("swsh", "k", "n", "pokemon", (), ("f",), "k")
    checks = radio.run_checks(cfg, {"swsh": Catalog("swsh", [ev]), "frlg": Catalog("frlg")},
                              find=lambda: "/dev/ttyACM0", hello_fn=lambda p, c: "idf=v6.1")
    assert [(c.name, c.ok) for c in checks] == [
        ("Placa", True), ("prod.keys", True), ("Sword/Shield", True), ("FireRed/LeafGreen", False)]
    assert "atualizar-catalogo" in checks[3].message


def test_run_checks_no_board(cfg):
    checks = radio.run_checks(cfg, {}, find=lambda: None, hello_fn=None)
    assert checks[0].ok is False
    assert "Plugue a placa" in checks[0].message
