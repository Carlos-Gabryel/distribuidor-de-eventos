"""Mantém o host no ar: sobe o processo, lê o log, reinicia quando cai. Nada de interface."""
from __future__ import annotations

import os
import subprocess
import threading
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Callable

from distrib.games.base import Job, Update

EVENT_TEXT = {"delivered": "entregue", "party_full": "equipe cheia",
              "not_delivered": "não entregue"}


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
                 retry_delay: float = 3.0, clock=time.monotonic):
        self.mode, self.parse_line, self.job_factory = mode, parse_line, job_factory
        self.log_path, self.find_port = log_path, find_port
        self.max_failures, self.retry_delay, self.clock = max_failures, retry_delay, clock
        self._lock = threading.Lock()
        self._status = Status()
        self._stop = threading.Event()
        self._paused = threading.Event()
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
            self._thread.join(timeout=15)
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
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%H:%M:%S} {line}\n")

    def _kill(self) -> None:
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

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
            self._set(state="starting", label=job.label, channel=None)
            self._log(f"=== início: {job.label} ({port})")
            reached_air = self._run(job)
            if self._stop.is_set() or self._paused.is_set():
                continue
            code = self._proc.returncode
            self._log(f"=== fim: código {code}")
            if reached_air:
                failures = 0
            if self.mode == "session" and code in (0, 1, 124):
                continue                    # sessão terminou normalmente; próximo console
            failures += 1
            self._set(restarts=self.status().restarts + 1)
            if failures >= self.max_failures:
                self._set(state="failed", since=None)
                return
            self._stop.wait(self.retry_delay)

    def _run(self, job: Job) -> bool:
        env = {**os.environ, **job.env}
        self._proc = subprocess.Popen(job.argv, cwd=job.cwd, env=env, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, text=True, bufsize=1)
        reached_air = False
        for line in self._proc.stdout:
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
                changes.update(state="on_air", since=self.status().since or self.clock())
            elif update.state == "console":
                changes["state"] = "console"
            elif update.state in EVENT_TEXT:
                changes["last_event"] = EVENT_TEXT[update.state]
                if update.state == "delivered":
                    changes["deliveries"] = self.status().deliveries + 1
            self._set(**changes)
        self._proc.wait()
        return reached_air
