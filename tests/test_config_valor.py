import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "windows" / "config_valor.py"


def run(project, key, home="/home/alguem"):
    out = subprocess.run([sys.executable, str(SCRIPT), str(project), key], capture_output=True,
                         text=True, env={"HOME": home}, check=True)
    return out.stdout.strip()


def test_reads_and_expands(tmp_path):
    (tmp_path / "config.toml").write_text(
        'pokeldn_dir = "~/pokeldn"\npython = "~/.venvs/pokeldn/bin/python"\nkeys = "~/.switch/prod.keys"\n',
        encoding="utf-8")
    assert run(tmp_path, "python") == "/home/alguem/.venvs/pokeldn/bin/python"
    assert run(tmp_path, "keys") == "/home/alguem/.switch/prod.keys"


def test_local_overrides(tmp_path):
    (tmp_path / "config.toml").write_text('pokeldn_dir = "~/pokeldn"\n', encoding="utf-8")
    (tmp_path / "config.local.toml").write_text('pokeldn_dir = "/mnt/c/x"\n', encoding="utf-8")
    assert run(tmp_path, "pokeldn_dir") == "/mnt/c/x"
