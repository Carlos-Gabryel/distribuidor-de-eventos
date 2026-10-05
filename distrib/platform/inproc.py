"""Filhos em thread, para onde não há como criar outro processo (Android).

`InProcPopen` imita o subconjunto do `subprocess.Popen` que o app usa e roda `runner.child` numa
thread daemon. A saída vai para uma fila por um proxy de `sys.stdout`/`sys.stderr` instalado uma
única vez.

Regra de roteamento: com um job ativo, toda escrita vinda de qualquer thread, exceto as que já
existiam quando o job começou (UI, main), vai para a fila do job. Assim as threads criadas pelo
próprio job (leitores do pokeldn, trio) também caem na fila. O resto vai para o stream original.
Um job por vez.
"""
from __future__ import annotations

import ctypes
import os
import queue
import subprocess
import sys
import threading
import traceback
from pathlib import Path

_END = object()
_job_lock = threading.Lock()      # um job por vez
_install_lock = threading.Lock()
_active: "InProcPopen | None" = None


class _Router:
    """Substitui sys.stdout/sys.stderr; encaminha a escrita conforme a regra do módulo."""

    def __init__(self, original, name: str) -> None:
        self._original = original
        self._name = name

    def write(self, text: str) -> int:
        job = _active
        if job is not None and job._owns(threading.get_ident()):
            return job._feed(self._name, text)
        return self._original.write(text)

    def flush(self) -> None:
        job = _active
        if job is None or not job._owns(threading.get_ident()):
            self._original.flush()

    def __getattr__(self, attr):
        return getattr(self._original, attr)


def _install() -> None:
    with _install_lock:
        for name in ("stdout", "stderr"):
            stream = getattr(sys, name)
            if stream is not None and not isinstance(stream, _Router):
                setattr(sys, name, _Router(stream, name))


def _interrupt(tid: int) -> None:
    hit = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(tid),
                                                     ctypes.py_object(KeyboardInterrupt))
    if hit > 1:                                   # padrão: desfaz se atingiu mais de uma thread
        ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(tid), None)


def _release_radio() -> None:
    """O pokeldn abre a placa uma vez e a guarda em esp32_wlan._radio (num processo próprio, ela
    morre com ele). Em thread, o próximo job reaproveitaria uma conexão USB que o quiet já tomou.
    O esp32_wlan.use() também registra em ldn.wlan uma factory presa a esse rádio: sem zerá-la,
    o próximo host nem abre a placa e manda os comandos para o rádio fechado."""
    ldn_wlan = sys.modules.get("ldn.wlan")
    if ldn_wlan is not None:
        ldn_wlan.set_factory(None)
    wlan = sys.modules.get("pokeldn.ldn.esp32_wlan")
    radio = getattr(wlan, "_radio", None)
    if radio is None:
        return
    wlan._radio = None
    try:
        radio.close()
    except Exception:  # noqa: BLE001 - a placa pode já ter sumido
        traceback.print_exc()


class _Stdin:
    def __init__(self, proc: "InProcPopen") -> None:
        self._proc = proc

    def close(self) -> None:
        self._proc._interrupt()

    def write(self, _text: str) -> int:
        return 0

    def flush(self) -> None:
        pass


class InProcPopen:
    def __init__(self, argv, cwd=None, env=None, stderr=None, **_) -> None:
        from distrib import runner
        modes = [i for i, a in enumerate(argv) if a in runner.MODES]
        if not modes:
            raise ValueError(f"argv sem {runner.MODES}: {list(argv)}")
        if not _job_lock.acquire(timeout=10):
            raise RuntimeError("já há um job em thread rodando")
        _install()
        self._argv = list(argv[modes[0]:])
        self._cwd = Path(cwd) if cwd else Path.cwd()
        self._merge = stderr == subprocess.STDOUT
        self._queue: queue.Queue = queue.Queue()
        self._partial = {"stdout": "", "stderr": ""}
        self._err: list[str] = []
        self._saved_env: dict[str, str | None] = {}
        self._excluded = {t.ident for t in threading.enumerate()}
        self.returncode: int | None = None
        self.stdin = _Stdin(self)
        self.stdout = self._lines()
        self._env = env
        self._thread = threading.Thread(target=self._main, daemon=True, name="inproc-job")
        global _active
        _active = self
        self._apply_env()
        self._thread.start()

    def _owns(self, ident: int) -> bool:
        return ident not in self._excluded

    def _apply_env(self) -> None:
        for key, value in (self._env or {}).items():
            if os.environ.get(key) != value:
                self._saved_env[key] = os.environ.get(key)
                os.environ[key] = value

    def _restore_env(self) -> None:
        for key, old in self._saved_env.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
        self._saved_env.clear()

    def _feed(self, name: str, text: str) -> int:
        if name == "stderr" and not self._merge:
            self._err.append(text)
            return len(text)
        buf = self._partial[name] + text
        *done, self._partial[name] = buf.split("\n")
        for line in done:
            self._queue.put(line + "\n")
        return len(text)

    def _lines(self):
        while (item := self._queue.get()) is not _END:
            yield item

    def _main(self) -> None:
        from distrib import runner
        code = 0
        try:
            runner.child(self._argv, self._cwd, inproc=True)
        except SystemExit as exc:
            arg = exc.code
            code = 0 if arg is None else arg if isinstance(arg, int) else 1
            if isinstance(arg, str):
                self._feed("stderr", arg + "\n")
        except BaseException:
            code = 1
            self._feed("stderr", traceback.format_exc())
        finally:
            global _active
            for name, rest in self._partial.items():
                if rest:
                    self._queue.put(rest)
                    self._partial[name] = ""
            self.returncode = code
            _active = None
            self._restore_env()
            _release_radio()
            self._queue.put(_END)
            _job_lock.release()

    def _interrupt(self) -> None:
        if self._thread.is_alive() and self._thread.ident:
            _interrupt(self._thread.ident)

    def poll(self) -> int | None:
        return None if self._thread.is_alive() or self.returncode is None else self.returncode

    def wait(self, timeout: float | None = None) -> int:
        self._thread.join(timeout)
        if self._thread.is_alive():
            raise subprocess.TimeoutExpired(self._argv, timeout)
        return self.returncode

    def terminate(self) -> None:
        self._interrupt()

    def kill(self) -> None:
        self._interrupt()
        self._thread.join(5)
        if self._thread.is_alive():
            self.returncode = -9


def run(argv, cwd=None, env=None, timeout=None, **_) -> subprocess.CompletedProcess:
    """Equivalente de `subprocess.run(capture_output=True, text=True)` para o job em thread."""
    proc = InProcPopen(argv, cwd=cwd, env=env)
    out: list[str] = []
    reader = threading.Thread(target=lambda: out.extend(proc.stdout), daemon=True)
    reader.start()
    try:
        proc.wait(timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        reader.join(1)
        raise subprocess.TimeoutExpired(argv, timeout, output="".join(out)) from None
    reader.join(5)
    return subprocess.CompletedProcess(argv, proc.returncode, "".join(out), "".join(proc._err))
