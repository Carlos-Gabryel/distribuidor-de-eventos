import os
import sys

from distrib.pokeldn_path import ensure_importable


def test_macos_aponta_o_pkhex_empacotado(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("POKELDN_PKHEX", "x")
    monkeypatch.delenv("POKELDN_PKHEX")
    monkeypatch.setattr(sys, "path", list(sys.path))
    pkhex = tmp_path / "services" / "pkhex" / "dist" / "pokeldn-pkhex"
    pkhex.parent.mkdir(parents=True)
    pkhex.write_bytes(b"")
    ensure_importable(tmp_path)
    assert os.environ["POKELDN_PKHEX"] == str(pkhex)
