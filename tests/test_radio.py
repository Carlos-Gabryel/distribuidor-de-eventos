import subprocess
from types import SimpleNamespace as NS

import pytest

from distrib import radio, runner


def ports(*items):
    return lambda: [NS(device=d, vid=v, pid=p) for d, v, p in items]


def test_list_boards_names_bridges_and_skips_virtual_ports():
    boards = radio.list_boards(ports(("COM7", 0x10C4, 0xEA60), ("COM1", None, None),
                                     ("COM5", 0x1A86, 0x55D4), ("COM9", 0x1234, 0x5678)))
    assert boards == [radio.Port("COM5", "CH9102"), radio.Port("COM7", "CP210x"),
                      radio.Port("COM9", "desconhecida")]


def test_find_port_single_and_ambiguous():
    assert radio.find_port(ports(("COM5", 0x1A86, 0x55D4), ("COM1", None, None))) == "COM5"
    assert radio.find_port(ports()) is None
    assert radio.find_port(ports(("COM5", 0x1A86, 0x55D4), ("COM7", 0x10C4, 0xEA60))) is None


def test_every_known_bridge_with_a_driver_has_a_link():
    for bridge in ("CP210x", "CH340", "CH9102"):
        assert radio.DRIVERS[bridge].startswith("https://")


def test_hello_ok_and_error(cfg):
    seen = {}

    def ok(argv, **kw):
        seen["argv"], seen["kw"] = argv, kw
        return subprocess.CompletedProcess(argv, 0, "x\nESP32 pokeldn radio v7\n", "")

    assert radio.hello("COM5", cfg, run=ok) == "ESP32 pokeldn radio v7"
    assert seen["argv"] == runner.command("--module", "distrib.runners.hello", "COM5")
    assert runner.MANAGED not in seen["kw"]["env"]

    def bad(argv, **kw):
        return subprocess.CompletedProcess(argv, 1, "", "Traceback\nPermissionError: Access is denied")

    with pytest.raises(radio.RadioError, match="Access is denied"):
        radio.hello("COM5", cfg, run=bad)


def test_hello_timeout(cfg):
    def slow(argv, **kw):
        raise subprocess.TimeoutExpired(argv, 20)

    with pytest.raises(radio.RadioError, match="não respondeu"):
        radio.hello("COM5", cfg, run=slow)
