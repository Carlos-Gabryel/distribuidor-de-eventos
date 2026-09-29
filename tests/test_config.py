from pathlib import Path

from distrib import config as configmod


def _project(tmp_path, local=None):
    (tmp_path / "config.toml").write_text(
        'pokeldn_dir = "~/pokeldn"\npython = "~/.venvs/pokeldn/bin/python"\n'
        'keys = "~/.switch/prod.keys"\n', encoding="utf-8")
    if local:
        (tmp_path / "config.local.toml").write_text(local, encoding="utf-8")
    return tmp_path


def test_tilde_uses_distrib_user_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DISTRIB_USER_HOME", "/home/alguem")
    cfg = configmod.load(_project(tmp_path))
    assert cfg.pokeldn_dir == Path("/home/alguem/pokeldn")
    assert cfg.keys == Path("/home/alguem/.switch/prod.keys")
    assert cfg.catalog_dir == tmp_path / "catalog"
    assert cfg.frlg_idle_timeout == 120


def test_local_file_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("DISTRIB_USER_HOME", "/home/alguem")
    cfg = configmod.load(_project(tmp_path, 'pokeldn_dir = "/mnt/c/x/pokeldn"\n'))
    assert cfg.pokeldn_dir == Path("/mnt/c/x/pokeldn")
    assert cfg.python == Path("/home/alguem/.venvs/pokeldn/bin/python")


def test_real_config_points_at_a_pokeldn_checkout():
    cfg = configmod.load()
    assert (cfg.pokeldn_dir / "bin" / "swsh_gift_host.py").exists()
