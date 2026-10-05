"""android_env.apply com IS_ANDROID simulado (o estado global é restaurado a cada teste)."""
import hashlib
import os
import sys

import pytest
import serial

from distrib import config as configmod
from distrib.platform import android_env, android_usb
from distrib.pokeldn_path import ensure_importable

RAIZ = configmod.PROJECT_DIR / "vendor" / "pokeldn"


@pytest.fixture
def android(monkeypatch, tmp_path):
    ensure_importable(RAIZ)
    from pokeldn import pokemon
    monkeypatch.setattr(android_env, "IS_ANDROID", True)
    monkeypatch.setattr(android_env, "_applied", False)
    monkeypatch.setattr(sys, "exit", sys.exit)
    monkeypatch.setattr(serial, "Serial", serial.Serial)
    monkeypatch.setattr(serial, "serial_for_url", serial.serial_for_url)
    monkeypatch.setattr(pokemon.SERVICE, "validate_gift", pokemon.SERVICE.validate_gift)
    monkeypatch.setenv("POKELDN_L2", "tap")
    monkeypatch.setenv("ESPTOOL_CFGFILE", "")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(android_usb, "_java", Java())
    return configmod.load(data_dir=tmp_path / "data", root=configmod.PROJECT_DIR), pokemon


class Java:
    def __init__(self):
        self.screen = []

    def set_keep_screen_on(self, on):
        self.screen.append(on)


def test_apply_prepara_o_ambiente(android):
    cfg, pokemon = android
    android_env.apply(cfg)
    assert os.environ["POKELDN_L2"] == "userspace"
    assert os.getcwd() == str(cfg.pokeldn_dir)
    assert serial.Serial is android_usb.UsbSerial
    assert serial.serial_for_url("usb:x").port == "usb:x"
    assert (cfg.data_dir / "esptool.cfg").exists()
    assert os.environ["ESPTOOL_CFGFILE"] == str(cfg.data_dir / "esptool.cfg")
    assert pokemon.SERVICE.validate_gift.__name__ == "validate_offline"


def test_sys_exit_so_lanca_systemexit(android):
    cfg, _ = android
    sys.exit = lambda code=None: pytest.fail("flet_exit fecharia o app")
    android_env.apply(cfg)
    with pytest.raises(SystemExit) as info:
        sys.exit(3)
    assert info.value.code == 3


def test_apply_e_idempotente(android):
    cfg, pokemon = android
    android_env.apply(cfg)
    validate = pokemon.SERVICE.validate_gift
    sys.exit = lambda code=None: None            # o sys.exit é refeito a cada chamada
    android_env.apply(cfg)
    assert pokemon.SERVICE.validate_gift is validate
    with pytest.raises(SystemExit):
        sys.exit()


def test_apply_nao_faz_nada_no_desktop(android, monkeypatch):
    cfg, pokemon = android
    monkeypatch.setattr(android_env, "IS_ANDROID", False)
    before = sys.exit
    android_env.apply(cfg)
    assert sys.exit is before and os.environ["POKELDN_L2"] == "tap"


def test_validate_gift_usa_o_catalogo(android):
    cfg, pokemon = android
    from pokeldn.swsh import wc8
    rec = bytes(wc8.seal(bytearray(wc8.RECORD)))
    android_env.apply(cfg)
    validate = pokemon.SERVICE.validate_gift
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(rec).hexdigest()
    (cfg.data_dir / "swsh_validated.json").write_text(
        '{"records": {"%s": {"ok": true, "file": "a.wc8"}}}' % sha, encoding="utf-8")
    validate(rec)                                        # aprovado
    outro = bytes(wc8.seal(bytearray(wc8.RECORD)[:-1] + b"\x01"))
    with pytest.raises(pokemon.BuilderError):
        validate(outro)                                  # fora do catálogo
    with pytest.raises(pokemon.BuilderError):
        validate(b"curto")                               # sem selo


def test_keep_screen_on(android, monkeypatch):
    android_env.keep_screen_on(True)
    android_env.keep_screen_on(False)
    assert android_usb.get_java().screen == [True, False]
    monkeypatch.setattr(android_env, "IS_ANDROID", False)
    android_env.keep_screen_on(True)                     # no desktop não faz nada
    assert android_usb.get_java().screen == [True, False]
