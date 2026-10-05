"""A fachada que a interface usa: estado observável (Snapshot) + ações. Nada de Flet aqui.

As ações que bloqueiam (start, stop, flash_board, download_catalog, check_update) são chamadas
pela interface numa thread. Cada mudança de estado vira um Snapshot novo entregue aos inscritos,
de qualquer thread.
"""
from __future__ import annotations

import re
import threading
import time
import traceback
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Callable

from distrib import __version__, board, radio, update
from distrib.catalog import Catalog, Event, Group, group_events, load_index, search_groups
from distrib.config import Config
from distrib.distributor import Distributor
from distrib.platform import IS_ANDROID
from distrib.species import name as species_name
from distrib.sprites import SpriteCache

_KEY_LINE = re.compile(r"^\s*\w+\s*=\s*[0-9a-fA-F]+\s*$")
LOG_LINES = 300
BOARD_POLL = 2.0
RUN_POLL = 0.5
UPDATE_EVERY = 6 * 3600
BUSY_HINTS = ("PermissionError", "Access is denied", "Acesso negado", "could not open port")

MSG_NONE = "Plugue a placa no USB. Se ela já está plugada, instale o driver na aba Placa."
MSG_MANY = "Há mais de uma placa plugada. Deixe só a do Distribuidor."
MSG_BUSY = "Outro programa está usando a {port}. Feche-o e replugue a placa."
MSG_SILENT = "A placa em {port} não respondeu. Use “Preparar placa” na aba Placa."
MSG_LOST = "Placa desconectada. Reconecte o cabo USB; a distribuição continua quando ela voltar."


@dataclass(frozen=True)
class BoardInfo:
    kind: str = "checking"
    port: str | None = None
    bridge: str = ""
    message: str = "Procurando a placa…"

    @property
    def ok(self) -> bool:
        return self.kind == "ready"


@dataclass(frozen=True)
class RunInfo:
    game: str
    event: Event
    state: str = "starting"
    since: float | None = None
    channel: int | None = None
    deliveries: int = 0
    last_event: str = ""
    detail: str = ""


@dataclass(frozen=True)
class Snapshot:
    board: BoardInfo = BoardInfo()
    keys_ok: bool = False
    catalog_ok: bool = False
    run: RunInfo | None = None
    log: tuple[str, ...] = ()
    flash_progress: float | None = None
    update_state: str = "none"
    update_version: str = ""
    update_url: str = ""            # Android: página do Release (não baixa nem aplica)

    @property
    def ready(self) -> bool:
        return self.keys_ok and self.catalog_ok and self.board.ok


class Service:
    def __init__(self, cfg: Config, adapters: dict | None = None, *, comports=None, hello=None,
                 make_distributor=None, sprites: SpriteCache | None = None,
                 latest=update.latest, download=update.download, exe_path: Path | None = None,
                 clock=time.monotonic, keep_screen_on=None):
        if adapters is None:
            from distrib.games import ADAPTERS as adapters
        if comports is None:
            comports = radio.system_comports
        self.cfg, self.adapters, self.clock = cfg, adapters, clock
        if keep_screen_on is None:
            from distrib.platform.android_env import keep_screen_on
        self._keep_screen_on = keep_screen_on       # tela ligada durante a distribuição (Android)
        self.comports = comports
        self.hello = hello or (lambda port: radio.hello(port, cfg))
        self.make_distributor = make_distributor or self._default_distributor
        self.sprites = sprites or SpriteCache(cfg.sprites_dir)
        self._latest, self._download, self.exe_path = latest, download, exe_path
        self._lock = threading.RLock()
        self._listeners: list[Callable[[Snapshot], None]] = []
        self._catalogs: dict[str, Catalog] = {}
        self._groups: dict[str, list[Group]] = {}
        self._hidden: dict[str, int] = {}
        self._distributor: Distributor | None = None
        self._log: list[str] = []
        self._ready_update: Path | None = None
        self._last_port: str | None = None
        self._stop = threading.Event()
        self._snap = Snapshot(keys_ok=self._stored_keys_ok(), catalog_ok=self._load_catalogs())

    # ---- estado ----
    def snapshot(self) -> Snapshot:
        with self._lock:
            return self._snap

    def subscribe(self, callback: Callable[[Snapshot], None]) -> None:
        with self._lock:
            self._listeners.append(callback)
        callback(self.snapshot())

    def _publish(self, **changes) -> None:
        with self._lock:
            new = replace(self._snap, **changes)
            if new == self._snap:
                return
            self._snap = new
            listeners = list(self._listeners)
        for callback in listeners:
            try:
                callback(new)
            except Exception:
                traceback.print_exc()       # uma tela com defeito não derruba o serviço

    # ---- configuração ----
    @staticmethod
    def _keys_valid(data: bytes) -> bool:
        lines = data.decode("utf-8", errors="replace").splitlines()
        return sum(1 for line in lines if _KEY_LINE.match(line)) >= 10

    def _stored_keys_ok(self) -> bool:
        try:
            return self._keys_valid(self.cfg.keys.read_bytes())
        except OSError:
            return False

    def set_keys(self, source: Path | bytes) -> None:
        """Guarda o prod.keys. `source` é um caminho ou o conteúdo (no Android o seletor não dá caminho usável)."""
        data = source if isinstance(source, bytes) else source.read_bytes()
        if not self._keys_valid(data):
            raise ValueError("Esse arquivo não parece um prod.keys "
                             "(esperado: linhas 'nome = hexadecimal').")
        self.cfg.keys.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(source, bytes) or source.resolve() != self.cfg.keys.resolve():
            self.cfg.keys.write_bytes(data)
        self._publish(keys_ok=True)

    def _load_catalogs(self) -> bool:
        for game in self.adapters:
            catalog = load_index(game, self.cfg.catalog_dir / game / "index.json")
            self._hidden[game] = 0
            if IS_ANDROID and hasattr(self.adapters[game], "approved"):   # só os aprovados pelo PKHeX
                events, self._hidden[game] = self.adapters[game].approved(catalog.events, self.cfg)
                catalog = replace(catalog, events=events)
            self._catalogs[game] = catalog
            self._groups[game] = group_events(catalog.events, species_name)
        return all(self._catalogs[game].events for game in self.adapters)

    def download_catalog(self, log: Callable[[str], None]) -> None:
        from distrib import download
        download.update_catalogs(self.cfg, tuple(self.adapters), log=log)
        self._publish(catalog_ok=self._load_catalogs())

    def event_count(self, game: str) -> int:
        return len(self._catalogs[game].events)

    def hidden_count(self, game: str) -> int:
        """Eventos que o catálogo validado recusou e que a grade não mostra (Android)."""
        return self._hidden.get(game, 0)

    def groups(self, game: str, text: str = "") -> list[Group]:
        return search_groups(self._groups[game], text)

    # ---- distribuição ----
    def _default_distributor(self, game: str, event: Event) -> Distributor:
        adapter = self.adapters[game]
        log = self.cfg.logs_dir / f"{date.today():%Y-%m-%d}.log"
        return Distributor(adapter.mode, adapter.parse_line,
                           lambda port: adapter.build_job(event, self.cfg, port), log,
                           lambda: radio.find_port(self.comports), on_line=self._append_log)

    def _append_log(self, line: str) -> None:
        with self._lock:
            self._log.append(line)
            del self._log[:-LOG_LINES]
            log = tuple(self._log)
        if IS_ANDROID:      # sem acesso aos arquivos do app: o log da sessão vai também para o logcat
            print(f"[job] {line}", flush=True)
        self._publish(log=log)

    def start(self, game: str, event: Event) -> None:
        if not self.snapshot().ready:
            raise RuntimeError("configuração incompleta")
        self.stop()
        with self._lock:
            self._log.clear()
        self._distributor = self.make_distributor(game, event)
        self._publish(run=RunInfo(game, event), log=())
        self._keep_screen_on(True)
        self._distributor.start()

    def pause(self) -> None:
        if self._distributor is not None:
            self._distributor.pause()
            self._sync_run()

    def resume(self) -> None:
        if self._distributor is not None:
            self._distributor.resume()
            self._sync_run()

    def stop(self) -> None:
        distributor, self._distributor = self._distributor, None
        if distributor is not None:
            distributor.stop()
        self._keep_screen_on(False)
        self._publish(run=None)

    def _sync_run(self) -> None:
        distributor, run = self._distributor, self.snapshot().run
        if distributor is None or run is None:
            return
        st = distributor.status()
        self._publish(run=replace(run, state=st.state, since=st.since, channel=st.channel,
                                  deliveries=st.deliveries, last_event=st.last_event,
                                  detail=st.detail))

    # ---- placa ----
    def check_board(self, force: bool = False) -> None:
        snap = self.snapshot()
        if snap.flash_progress is not None:
            return
        if snap.run is not None:
            if snap.run.state == "no_board":
                self._last_port = None
                self._publish(board=BoardInfo("none", message=MSG_LOST))
            elif not snap.board.ok:
                port = radio.find_port(self.comports)
                self._publish(board=BoardInfo("ready", port, snap.board.bridge, "Em uso pela distribuição"))
            return
        boards = radio.list_boards(self.comports)
        if not boards:
            self._last_port = None
            self._publish(board=BoardInfo("none", message=MSG_NONE))
            return
        if len(boards) > 1:
            self._last_port = None
            self._publish(board=BoardInfo("many", message=MSG_MANY))
            return
        port = boards[0]
        if port.device == self._last_port and not force:
            return
        self._last_port = port.device
        self._publish(board=BoardInfo("checking", port.device, port.bridge,
                                      f"Conversando com a placa em {port.device}…"))
        try:
            text = self.hello(port.device)
        except radio.RadioError as exc:
            busy = any(hint in str(exc) for hint in BUSY_HINTS)
            message = (MSG_BUSY if busy else MSG_SILENT).format(port=port.device)
            self._publish(board=BoardInfo("busy" if busy else "silent", port.device, port.bridge, message))
            return
        self._publish(board=BoardInfo("ready", port.device, port.bridge,
                                      f"{port.bridge} · {port.device} · {text}"))

    def flash_board(self) -> int:
        if self.snapshot().run is not None:
            raise RuntimeError("Pare a distribuição antes de preparar a placa.")
        boards = radio.list_boards(self.comports)
        if len(boards) != 1:
            raise RuntimeError(MSG_NONE if not boards else MSG_MANY)
        port = boards[0]
        with self._lock:
            self._log.clear()
        self._publish(flash_progress=0.0, log=(),
                      board=BoardInfo("flashing", port.device, port.bridge, "Gravando o firmware…"))
        try:
            code = board.flash(port.device, self.cfg, self._append_log,
                               lambda value: self._publish(flash_progress=value))
        finally:
            self._publish(flash_progress=None)
        self._last_port = None
        self.check_board(force=True)
        return code

    # ---- atualização ----
    def check_update(self) -> None:
        if self.snapshot().update_state in ("downloading", "ready", "available"):
            return
        try:
            release = self._latest()
            if not update.newer(release, __version__):
                return
            if IS_ANDROID:       # instalar um .apk é com o usuário: o aviso abre a página do Release
                self._publish(update_state="available", update_version=release.tag,
                              update_url=release.html_url or release.url)
                return
            self._publish(update_state="downloading", update_version=release.tag)
            self._ready_update = self._download(release, self.cfg.data_dir / "updates")
            self._publish(update_state="ready")
        except (OSError, ValueError, update.UpdateError):
            downloading = self.snapshot().update_state == "downloading"
            self._publish(update_state="error" if downloading else "none")

    def apply_update(self) -> bool:
        """True quando a versão nova já foi aberta e este app deve fechar."""
        if self._ready_update is None or self.exe_path is None or self.snapshot().run is not None:
            return False
        try:
            update.apply(self._ready_update, self.exe_path)
        except OSError:
            self._publish(update_state="error")
            return False
        return True

    # ---- ciclo de vida ----
    def start_background(self, updates: bool) -> None:
        threading.Thread(target=self._board_loop, daemon=True).start()
        if updates:
            threading.Thread(target=self._update_loop, daemon=True).start()

    def _board_loop(self) -> None:
        next_board = 0.0
        while not self._stop.is_set():
            try:
                self._sync_run()
                if self.clock() >= next_board:
                    self.check_board()
                    next_board = self.clock() + BOARD_POLL
            except Exception:
                traceback.print_exc()
            self._stop.wait(RUN_POLL)

    def _update_loop(self) -> None:
        while not self._stop.is_set():
            self.check_update()
            self._stop.wait(UPDATE_EVERY)

    def shutdown(self) -> None:
        self._stop.set()
        self.stop()
