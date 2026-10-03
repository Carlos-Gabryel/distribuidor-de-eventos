import subprocess
import sys

from distrib import runner
from distrib.config import PROJECT_DIR


def test_command_in_source_mode():
    assert runner.command("--run", "bin/x.py", "-v") == [
        sys.executable, "-u", str(PROJECT_DIR / "main.py"), "--run", "bin/x.py", "-v"]


def test_command_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert runner.command("--module", "m") == [sys.executable, "--module", "m"]


def test_is_child():
    assert runner.is_child(["--run", "bin/x.py"])
    assert runner.is_child(["--module", "a.b", "x"])
    assert not runner.is_child([])
    assert not runner.is_child(["--run"])
    assert not runner.is_child(["outro", "x"])


def test_child_env_managed_flag():
    assert runner.child_env({"A": "1"})[runner.MANAGED] == "1"
    assert runner.child_env({"A": "1"})["A"] == "1"
    assert runner.MANAGED not in runner.child_env(managed=False)


def _spawn(*argv, managed=True):
    return subprocess.Popen(runner.command(*argv), cwd=str(PROJECT_DIR),
                            env=runner.child_env(managed=managed), **runner.popen_kwargs())


def test_module_child_runs_and_exits_with_its_code():
    proc = _spawn("--module", "tests.child_script", "3", "ola", managed=False)
    out, _ = proc.communicate(timeout=60)
    assert "args ola" in out
    assert proc.returncode == 3


def test_closing_stdin_interrupts_a_managed_child():
    proc = _spawn("--module", "tests.child_script", "wait")
    assert proc.stdout.readline().strip() == "args"
    proc.stdin.close()
    assert proc.wait(timeout=20) == 130
    assert "interrompido" in proc.stdout.read()


def test_run_mode_runs_a_pokeldn_script():
    proc = _spawn("--run", "bin/swsh_gift_host.py", "--help", managed=False)
    out, _ = proc.communicate(timeout=120)
    assert proc.returncode == 0, out
    assert "--record" in out
