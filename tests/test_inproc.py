import subprocess
import sys
import threading

import pytest

from distrib import runner
from distrib.platform import inproc

MOD = "tests.fixtures.inproc_child"


def argv(*extra):
    return ["python", "main.py", "--module", MOD, *extra]


def test_desktop_usa_subprocess():
    assert runner.popen is subprocess.Popen
    assert runner.run is subprocess.run


def test_le_linhas_ate_o_fim(tmp_path):
    proc = inproc.InProcPopen(argv("quiet"), cwd=tmp_path, stderr=subprocess.STDOUT)
    assert list(proc.stdout) == ["a\n", "b\n", "c\n"]
    assert proc.wait(5) == 0
    assert proc.poll() == 0


def test_stdin_close_para_com_elegancia(tmp_path):
    proc = inproc.InProcPopen(argv(), cwd=tmp_path, stderr=subprocess.STDOUT)
    it = iter(proc.stdout)
    assert [next(it) for _ in range(3)] == ["a\n", "b\n", "c\n"]
    assert proc.poll() is None
    proc.stdin.close()
    assert list(it) == ["parado\n"]
    assert proc.wait(5) == 0


def test_terminate_e_kill(tmp_path):
    for stop in ("terminate", "kill"):
        proc = inproc.InProcPopen(argv(), cwd=tmp_path, stderr=subprocess.STDOUT)
        next(iter(proc.stdout))
        getattr(proc, stop)()
        proc.wait(5)
        assert proc.returncode == 0


def test_systemexit_e_excecao(tmp_path):
    assert inproc.run(argv("exit3"), cwd=tmp_path).returncode == 3
    done = inproc.run(argv("boom"), cwd=tmp_path)
    assert done.returncode == 1
    assert "falhou" in done.stderr


def test_run_captura_e_timeout(tmp_path):
    done = inproc.run(argv("quiet"), cwd=tmp_path)
    assert (done.returncode, done.stdout) == (0, "a\nb\nc\n")
    with pytest.raises(subprocess.TimeoutExpired):
        inproc.run(argv(), cwd=tmp_path, timeout=0.3)


def test_env_aplicado_e_restaurado(tmp_path, monkeypatch):
    monkeypatch.setenv("INPROC_X", "antes")
    seen = {}
    monkeypatch.setattr(inproc, "_active", None)
    proc = inproc.InProcPopen(argv(), cwd=tmp_path, env={"INPROC_X": "depois", "INPROC_Y": "1"},
                              stderr=subprocess.STDOUT)
    next(iter(proc.stdout))
    import os
    seen.update(x=os.environ["INPROC_X"], y=os.environ.get("INPROC_Y"))
    proc.terminate()
    proc.wait(5)
    assert seen == {"x": "depois", "y": "1"}
    assert os.environ["INPROC_X"] == "antes" and "INPROC_Y" not in os.environ


def test_threads_anteriores_escrevem_no_stream_original(tmp_path):
    proc = inproc.InProcPopen(argv(), cwd=tmp_path, stderr=subprocess.STDOUT)
    next(iter(proc.stdout))
    original = sys.stdout._original
    written, go = [], threading.Event()
    real_write = original.write
    original.write = lambda t: written.append(t) or len(t)
    t = threading.Thread(target=lambda: (go.wait(), sys.stdout.write("da-ui")))
    t.start()
    proc._excluded.add(t.ident)            # trata a thread como existente antes do job
    go.set()
    t.join()
    original.write = real_write
    proc.terminate()
    assert list(proc.stdout)[-1] == "parado\n"
    assert written == ["da-ui"]


def test_fim_do_job_fecha_o_radio_do_pokeldn(tmp_path, monkeypatch):
    """O pokeldn guarda a placa aberta em esp32_wlan._radio; em thread, o próximo job
    reaproveitaria uma conexão USB que o quiet já tomou."""
    import types

    class Radio:
        closed = False

        def close(self):
            self.closed = True

    radio = Radio()
    fake = types.ModuleType("pokeldn.ldn.esp32_wlan")
    fake._radio = radio
    monkeypatch.setitem(sys.modules, "pokeldn.ldn.esp32_wlan", fake)
    ldn_wlan = types.ModuleType("ldn.wlan")
    ldn_wlan.factory = "presa ao rádio velho"
    ldn_wlan.set_factory = lambda f: setattr(ldn_wlan, "factory", f)
    monkeypatch.setitem(sys.modules, "ldn.wlan", ldn_wlan)
    proc = inproc.InProcPopen(argv("quiet"), cwd=tmp_path, stderr=subprocess.STDOUT)
    list(proc.stdout)
    assert proc.wait(5) == 0
    assert radio.closed and fake._radio is None
    assert ldn_wlan.factory is None
