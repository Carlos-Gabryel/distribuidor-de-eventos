import struct
import sys
import threading
import time

from distrib import runner
from pokeldn.ldn import esp32
from distrib.runners import quiet as quietmod

INFO = bytes([esp32.PROTOCOL_VERSION]) + bytes(6) + bytes(6) + bytes([1]) + b"pokeldn radio"
FAST = ((921600, 0.3), (115200, 0.3))


class FakeSerial:
    """Serial falso: responde aos frames do pokeldn só nos bauds de `answers`."""

    def __init__(self, answers, opened):
        self.answers, self.opened = answers, opened
        self.port = self.baudrate = self.timeout = None
        self.dtr = self.rts = None
        self.closed = False
        self.commands = []
        self._out = bytearray()
        self._pending = bytearray()
        self._lock = threading.Lock()

    def open(self):
        self.opened.append(self)

    def close(self):
        self.closed = True

    def write(self, data):
        self._pending += data
        while 0 in self._pending:
            end = self._pending.index(0)
            frame, self._pending = bytes(self._pending[:end]), self._pending[end + 1:]
            if not frame:
                continue
            cmd, payload = esp32.decode_frame(frame)
            self.commands.append((cmd, payload))
            if self.baudrate not in self.answers:
                continue
            if cmd == esp32.CMD_HELLO:
                reply = esp32.encode_frame(esp32.MSG_INFO, INFO)
            elif cmd in (esp32.CMD_CHANNEL, esp32.CMD_BAUD):
                reply = esp32.encode_frame(esp32.MSG_RESULT, bytes([cmd]) + struct.pack("<i", 0))
            else:
                continue
            with self._lock:
                self._out += reply

    def read(self, n):
        with self._lock:
            data, self._out = bytes(self._out[:n]), self._out[n:]
        if not data:
            time.sleep(0.005)
        return data


def run(answers):
    opened = []
    ok = quietmod.quiet("COM9", serial_factory=lambda: FakeSerial(answers, opened),
                        attempts=FAST, sleep=lambda s: None)
    return ok, opened


def cmds(serial):
    return [c for c, _ in serial.commands]


def test_fast_baud_answers_then_baud_is_reset():
    ok, opened = run({921600})
    assert ok and len(opened) == 1
    s = opened[0]
    assert (s.port, s.baudrate, s.dtr, s.rts) == ("COM9", 921600, False, False)
    assert esp32.CMD_BAUD in cmds(s)
    assert dict(s.commands)[esp32.CMD_BAUD] == struct.pack("<I", 115200)
    assert s.closed


def test_slow_baud_answers_without_baud_command():
    ok, opened = run({115200})
    assert ok and len(opened) == 2
    assert esp32.CMD_BAUD not in cmds(opened[0]) + cmds(opened[1])
    assert all(s.closed for s in opened)


def test_no_answer_returns_false_and_closes_every_port():
    ok, opened = run(set())
    assert ok is False and len(opened) == 2
    assert all(s.closed for s in opened)


def test_quiet_info_returns_hello_text():
    opened = []
    text = quietmod.quiet_info("COM9", serial_factory=lambda: FakeSerial({115200}, opened),
                               attempts=FAST, sleep=lambda s: None)
    assert text == "pokeldn radio"


def child_calls(monkeypatch, radio, argv):
    calls = []
    monkeypatch.setattr(quietmod, "quiet", lambda port: calls.append(port) or True)
    monkeypatch.setattr(runner.runpy, "run_module", lambda *a, **k: None)
    monkeypatch.setattr(runner.runpy, "run_path", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", list(sys.argv))
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.delenv(runner.MANAGED, raising=False)
    if radio is None:
        monkeypatch.delenv("POKELDN_RADIO", raising=False)
    else:
        monkeypatch.setenv("POKELDN_RADIO", radio)
    from distrib.config import load
    runner.child(argv, load().pokeldn_dir)
    return calls


def test_child_quiets_before_host(monkeypatch):
    argv = ["--module", "distrib.runners.frlg_session"]
    assert child_calls(monkeypatch, "esp32:COM9", argv) == ["COM9"]
    assert child_calls(monkeypatch, "esp32:COM9", ["--run", "bin/swsh_gift_host.py"]) == ["COM9"]


def test_child_does_not_quiet_hello_or_without_radio(monkeypatch):
    assert child_calls(monkeypatch, "esp32:COM9", ["--module", "distrib.runners.hello", "COM9"]) == []
    assert child_calls(monkeypatch, None, ["--module", "distrib.runners.frlg_session"]) == []


def test_child_survives_quiet_failure(monkeypatch, capsys):
    def boom(port):
        raise OSError("porta em uso")

    monkeypatch.setattr(quietmod, "quiet", boom)
    monkeypatch.setattr(runner.runpy, "run_module", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", list(sys.argv))
    monkeypatch.delenv(runner.MANAGED, raising=False)
    monkeypatch.setenv("POKELDN_RADIO", "esp32:COM9")
    from distrib.config import load
    runner.child(["--module", "x"], load().pokeldn_dir)
    assert "[quiet] erro" in capsys.readouterr().out
