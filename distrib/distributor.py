"""Mantém o host no ar: sobe o processo, lê o log, reinicia quando cai. Nada de interface."""
from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Callable

from distrib import runner
from distrib.games.base import Job, Update

EVENT_TEXT = {"delivered": "entregue", "party_full": "equipe cheia",
              "not_delivered": "não entregue"}
# Códigos de fim normal de uma sessão FRLG: entregue, não entregue, ninguém veio.
SESSION_END_CODES = (0, 1, 124)


@dataclass(frozen=True)
class Status:
    state: str = "idle"
    label: str = ""
    since: float | None = None
    channel: int | None = None
    restarts: int = 0
    deliveries: int = 0
    last_event: str = ""
    detail: str = ""


class Distributor:
    def __init__(self, mode: str, parse_line: Callable[[str], Update | None],
                 job_factory: Callable[[str], Job], log_path: Path,
                 find_port: Callable[[], str | None], max_failures: int = 3,
                 retry_delay: float = 3.0, watch_interval: float = 1.0, clock=time.monotonic,
                 on_line: Callable[[str], None] | None = None, stop_grace: float = 15.0):
        self.mode, self.parse_line, self.job_factory = mode, parse_line, job_factory
        self.log_path, self.find_port = log_path, find_port
        self.max_failures, self.retry_delay, self.clock = max_failures, retry_delay, clock
        self.watch_interval, self.on_line, self.stop_grace = watch_interval, on_line, stop_grace
        self._lock = threading.Lock()           # protege o Status
        self._proc_lock = threading.Lock()      # protege criar/matar o processo do host
        self._status = Status()
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._board_lost = threading.Event()
        self._thread: threading.Thread | None = None
        self._proc: subprocess.Popen | None = None

    # ---- API ----
    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def status(self) -> Status:
        with self._lock:
            return self._status

    def start(self) -> None:
        self.stop()
        self._stop.clear()
        self._paused.clear()
        self._set(state="starting", restarts=0, deliveries=0, last_event="", detail="")
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._kill()
        if self._thread is not None:
            self._thread.join(timeout=20)
            if self._thread.is_alive():
                self._log("=== aviso: a thread do host não terminou; matando o processo de novo")
                self._kill()
            self._thread = None
        self._set(state="idle", since=None, channel=None)

    def pause(self) -> None:
        self._paused.set()
        self._kill()
        self._set(state="paused", since=None)

    def resume(self) -> None:
        self._paused.clear()
        self._set(state="starting")

    # ---- interno ----
    def _set(self, **changes) -> None:
        with self._lock:
            self._status = replace(self._status, **changes)

    def _log(self, line: str) -> None:
        stamped = f"{datetime.now():%H:%M:%S} {line}"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(stamped + "\n")
        if self.on_line is not None:
            self.on_line(stamped)

    def _kill(self) -> None:
        # Fechar o stdin vira KeyboardInterrupt no filho (distrib.runner): é assim que os hosts do
        # pokeldn desmontam a rede na placa. Um processo sem janela no Windows não recebe Ctrl+C.
        with self._proc_lock:
            proc = self._proc
            if proc is None or proc.poll() is not None:
                return

            def close_stdin():
                try:
                    if proc.stdin is not None:
                        proc.stdin.close()
                except OSError:
                    pass

            for send, wait in ((close_stdin, self.stop_grace), (proc.terminate, 5), (proc.kill, None)):
                send()
                try:
                    proc.wait(timeout=wait)
                    return
                except subprocess.TimeoutExpired:
                    continue

    def _spawn(self, job: Job) -> subprocess.Popen | None:
        # Checar "parar/pausar" e criar o processo sob o mesmo lock que o _kill usa: sem janela
        # em que um stop() chega entre a checagem e o Popen e deixa dois hosts na placa.
        with self._proc_lock:
            if self._stop.is_set() or self._paused.is_set():
                return None
            self._proc = runner.popen(job.argv, cwd=job.cwd, env=runner.child_env(job.env),
                                     **runner.popen_kwargs())
            return self._proc

    def _watch_board(self, proc: subprocess.Popen) -> None:
        # A placa pode sumir no meio: o host do SwSh não percebe e ficaria "no ar" para sempre.
        while proc.poll() is None:
            if self.find_port() is None:
                self._board_lost.set()
                self._log("=== placa desconectada no meio da distribuição")
                self._kill()
                return
            time.sleep(self.watch_interval)

    def _loop(self) -> None:
        failures = 0
        while not self._stop.is_set():
            if self._paused.is_set():
                time.sleep(0.05)
                continue
            port = self.find_port()
            if port is None:
                self._set(state="no_board", since=None)
                self._stop.wait(self.retry_delay)
                continue
            job = self.job_factory(port)
            self._board_lost.clear()
            proc = self._spawn(job)
            if proc is None:
                continue                    # parado ou pausado enquanto o job era montado
            self._set(state="starting", label=job.label, channel=None)
            self._log(f"=== início: {job.label} ({port})")
            reached_air = self._run(proc, job)
            if self._stop.is_set() or self._paused.is_set():
                continue
            code = proc.returncode
            self._log(f"=== fim: código {code}")
            if self._board_lost.is_set() or self.find_port() is None:
                self._set(state="no_board", since=None)
                continue                    # placa sumiu: não é falha do host
            if reached_air:
                failures = 0
            if self.mode == "session" and reached_air and code in SESSION_END_CODES:
                continue                    # sessão terminou normalmente; próximo console
            failures += 1
            self._set(restarts=self.status().restarts + 1)
            if failures >= self.max_failures:
                self._set(state="failed", since=None)
                return
            self._stop.wait(self.retry_delay)

    def _run(self, proc: subprocess.Popen, job: Job) -> bool:
        watcher = threading.Thread(target=self._watch_board, args=(proc,), daemon=True)
        watcher.start()
        reached_air = False
        for line in proc.stdout:
            line = line.rstrip("\n")
            self._log(line)
            update = self.parse_line(line)
            if update is None:
                continue
            changes = {}
            if update.channel is not None:
                changes["channel"] = update.channel
            if update.detail is not None:
                changes["detail"] = update.detail
            if update.state == "on_air":
                reached_air = True
                if not self._paused.is_set():
                    changes.update(state="on_air", since=self.status().since or self.clock())
            elif update.state == "console":
                changes["state"] = "console"
            elif update.state in EVENT_TEXT:
                changes["last_event"] = EVENT_TEXT[update.state]
                if update.state == "delivered":
                    changes["deliveries"] = self.status().deliveries + 1
                    if job.on_delivered is not None:
                        job.on_delivered()
            self._set(**changes)
        proc.wait()
        watcher.join(timeout=self.watch_interval * 2 + 1)
        return reached_air
