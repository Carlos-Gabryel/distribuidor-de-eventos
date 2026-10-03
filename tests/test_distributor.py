import sys
import time
from pathlib import Path

from distrib.distributor import Distributor
from distrib.games.base import Job
from distrib.games.frlg import FrlgAdapter
from distrib.games.swsh import SwshAdapter

FAKE = str(Path(__file__).parent / "fake_host.py")
HOSTING = "[    0.2s] Hosting. Waiting for the console to join (ssid=x..., channel 6)."


def job(code, *script):
    return lambda port: Job(argv=(sys.executable, FAKE, str(code), *script), label="Teste")


def wait_for(pred, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.02)
    return False


def make(tmp_path, mode, factory, find=lambda: "COM5", **kw):
    parse = SwshAdapter().parse_line if mode == "broadcast" else FrlgAdapter(None).parse_line
    return Distributor(mode, parse, factory, tmp_path / "log.txt", find,
                       retry_delay=0.05, watch_interval=0.05, **kw)


def test_broadcast_goes_on_air(tmp_path):
    d = make(tmp_path, "broadcast", job(0, "[host] AP up: ssid=x ch=6 us=y",
                                        "advertising comm id 0x1", "sleep:5"))
    d.start()
    assert wait_for(lambda: d.status().state == "on_air")
    st = d.status()
    assert st.channel == 6 and st.label == "Teste" and st.since is not None
    d.stop()
    assert d.status().state == "idle"
    assert "advertising comm id" in (tmp_path / "log.txt").read_text(encoding="utf-8")


def test_broadcast_restarts_then_gives_up(tmp_path):
    d = make(tmp_path, "broadcast", job(1, "RuntimeError: LDN host bring-up failed"))
    d.start()
    assert wait_for(lambda: d.status().state == "failed")
    st = d.status()
    assert st.restarts == 3
    assert "bring-up failed" in st.detail
    d.stop()


def test_on_air_resets_failure_streak(tmp_path):
    calls = []

    def factory(port):
        calls.append(port)
        if len(calls) % 2:
            return job(1, "RuntimeError: x")(port)
        return job(1, "advertising comm id 0x1", "sleep:0.1")(port)

    d = make(tmp_path, "broadcast", factory)
    d.start()
    assert wait_for(lambda: len(calls) >= 8)
    assert d.status().state != "failed"
    d.stop()


def test_session_counts_deliveries_and_restarts(tmp_path):
    d = make(tmp_path, "session", job(0, HOSTING, "Mystery Event script status: 2 (success)"))
    d.start()
    assert wait_for(lambda: d.status().deliveries >= 3)
    st = d.status()
    assert st.state != "failed" and st.last_event == "entregue"
    d.stop()


def test_session_idle_timeout_is_not_a_failure(tmp_path):
    d = make(tmp_path, "session", job(124, HOSTING))
    d.start()
    time.sleep(0.6)
    assert d.status().state != "failed"
    d.stop()


def test_session_party_full(tmp_path):
    d = make(tmp_path, "session", job(1, HOSTING,
                                      "Mystery Event script status: 3 (incompatible)"))
    d.start()
    assert wait_for(lambda: d.status().last_event == "equipe cheia")
    assert d.status().deliveries == 0
    d.stop()


def test_no_board_waits_without_counting_failures(tmp_path):
    present = {"port": None}
    d = make(tmp_path, "broadcast", job(0, "advertising comm id 0x1", "sleep:5"),
             find=lambda: present["port"])
    d.start()
    assert wait_for(lambda: d.status().state == "no_board")
    time.sleep(0.3)
    assert d.status().restarts == 0
    present["port"] = "COM5"
    assert wait_for(lambda: d.status().state == "on_air")
    d.stop()


def test_switch_stops_previous_process_first(tmp_path):
    d1 = make(tmp_path, "broadcast", job(0, "advertising comm id 0x1", "sleep:30"))
    d1.start()
    assert wait_for(lambda: d1.status().state == "on_air")
    proc = d1._proc
    d1.stop()
    assert proc.poll() is not None
    assert not d1.running


def test_pause_and_resume(tmp_path):
    d = make(tmp_path, "broadcast", job(0, "advertising comm id 0x1", "sleep:30"))
    d.start()
    assert wait_for(lambda: d.status().state == "on_air")
    d.pause()
    assert d.status().state == "paused"
    d.resume()
    assert wait_for(lambda: d.status().state == "on_air")
    d.stop()


def test_board_lost_mid_run_goes_no_board_then_recovers(tmp_path):
    t0 = time.monotonic()
    # porta presente, some de 0.5 s a 1.5 s, depois volta
    find = lambda: None if 0.5 < time.monotonic() - t0 < 1.5 else "COM5"
    d = make(tmp_path, "broadcast", job(0, "advertising comm id 0x1", "sleep:30"), find=find)
    d.start()
    assert wait_for(lambda: d.status().state == "on_air")
    assert wait_for(lambda: d.status().state == "no_board", timeout=3)
    assert wait_for(lambda: d.status().state == "on_air", timeout=5)
    assert d.status().restarts == 0
    d.stop()


def test_stop_during_slow_job_factory_leaves_no_process(tmp_path):
    def slow(port):
        time.sleep(0.3)
        return job(0, "advertising comm id 0x1", "sleep:30")(port)

    d = make(tmp_path, "broadcast", slow)
    d.start()
    time.sleep(0.1)
    d.stop()
    time.sleep(0.5)
    assert d._proc is None or d._proc.poll() is not None
    assert not d.running


def test_pause_right_before_spawn_does_not_start_a_host(tmp_path):
    def slow(port):
        time.sleep(0.3)
        return job(0, "advertising comm id 0x1", "sleep:30")(port)

    d = make(tmp_path, "broadcast", slow)
    d.start()
    time.sleep(0.1)
    d.pause()
    time.sleep(0.6)
    assert d.status().state == "paused"
    assert d._proc is None or d._proc.poll() is not None
    d.stop()


def test_session_crash_before_air_counts_failure(tmp_path):
    d = make(tmp_path, "session", job(1, "Traceback (most recent call last):", "RuntimeError: boom"))
    d.start()
    assert wait_for(lambda: d.status().state == "failed")
    assert d.status().restarts == 3
    d.stop()


def test_stop_interrupts_the_host_with_sigint(tmp_path):
    d = make(tmp_path, "broadcast", job(0, "advertising comm id 0x1", "sleep:30"))
    d.start()
    assert wait_for(lambda: d.status().state == "on_air")
    d.stop()
    assert "interrompido" in (tmp_path / "log.txt").read_text(encoding="utf-8")


def test_on_delivered_runs_once_per_delivery(tmp_path):
    calls = []
    factory = lambda port: Job(argv=(sys.executable, FAKE, "0", HOSTING,
                                     "Mystery Event script status: 2 (success)"),
                               label="Teste", on_delivered=lambda: calls.append(1))
    d = make(tmp_path, "session", factory)
    d.start()
    assert wait_for(lambda: d.status().deliveries >= 2)
    d.stop()
    assert len(calls) == d.status().deliveries >= 2


def test_on_line_gets_each_log_line_with_time(tmp_path):
    seen = []
    d = make(tmp_path, "broadcast", job(0, "advertising comm id 0x1", "sleep:5"), on_line=seen.append)
    d.start()
    assert wait_for(lambda: any("advertising comm id" in line for line in seen))
    d.stop()
    line = next(line for line in seen if "advertising" in line)
    assert line[2] == ":" and line[5] == ":"        # "HH:MM:SS texto"


def test_stop_terminates_a_host_that_ignores_stdin(tmp_path):
    d = make(tmp_path, "broadcast", job(0, "deaf", "advertising comm id 0x1", "sleep:30"),
             stop_grace=0.3)
    d.start()
    assert wait_for(lambda: d.status().state == "on_air")
    started = time.monotonic()
    d.stop()
    assert time.monotonic() - started < 8
    assert d.status().state == "idle"
