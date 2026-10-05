import sys
from pathlib import Path

from distrib import config as configmod


def test_paths_live_in_the_data_dir(tmp_path):
    cfg = configmod.load(data_dir=tmp_path, root=tmp_path / "root")
    assert cfg.data_dir == tmp_path
    assert cfg.keys == tmp_path / "prod.keys"
    assert cfg.catalog_dir == tmp_path / "catalog"
    assert cfg.state_dir == tmp_path / "state"
    assert cfg.logs_dir == tmp_path / "logs"
    assert cfg.sprites_dir == tmp_path / "sprites"
    assert cfg.pokeldn_dir == tmp_path / "root" / "vendor" / "pokeldn"
    assert cfg.firmware_dir == tmp_path / "root" / "firmware"
    assert cfg.frlg_idle_timeout == 120


def test_settings_file_overrides(tmp_path):
    (tmp_path / "config.toml").write_text("frlg_idle_timeout = 30\n", encoding="utf-8")
    assert configmod.load(data_dir=tmp_path).frlg_idle_timeout == 30


def test_default_data_dir_uses_localappdata(monkeypatch, tmp_path):
    monkeypatch.delenv("DISTRIB_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert configmod.default_data_dir() == tmp_path / "Distribuidor"


def test_env_overrides_the_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("DISTRIB_DATA_DIR", str(tmp_path / "x"))
    assert configmod.default_data_dir() == tmp_path / "x"


def test_frozen_root_is_meipass(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert configmod.resource_root() == tmp_path


def test_real_pokeldn_checkout():
    cfg = configmod.load()
    assert (cfg.pokeldn_dir / "bin" / "swsh_gift_host.py").exists()


def test_default_data_dir_no_android(monkeypatch, tmp_path):
    monkeypatch.delenv("DISTRIB_DATA_DIR", raising=False)
    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(tmp_path / "files" / "data"))
    monkeypatch.setattr(configmod, "IS_ANDROID", True)
    assert configmod.default_data_dir() == tmp_path / "files" / "data"
