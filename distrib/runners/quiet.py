"""Aquieta a placa antes de um host do pokeldn.

A placa real, depois de uma sessão anterior (ou de um host morto à força), pode estar em 921600 baud,
num canal qualquer e com fila de comandos. Aqui: canal 13 sem esperar resposta, HELLO, canal 13 de novo
e, se estava rápida, volta para 115200 (a velocidade em que os hosts abrem a porta).
Referência que funcionou na placa real: tests/fixtures/logs/quiet_then_host_task2.py.
"""
from __future__ import annotations

import struct
import time

import serial

from pokeldn.ldn import esp32

ATTEMPTS = ((921600, 1.5), (115200, 60.0))


def quiet_info(port: str, *, serial_factory=None, attempts=ATTEMPTS, sleep=time.sleep) -> str | None:
    """Aquieta a placa e devolve o texto do MSG_INFO (None se nenhuma tentativa deu certo).

    Sempre termina com a placa em 115200 baud. Erros ao abrir a porta (ex.: porta em uso)
    propagam para quem chamou.
    """
    factory = serial_factory or serial.Serial
    started = time.time()
    text = None
    for baud, hello_timeout in attempts:
        s = factory()
        s.port, s.baudrate, s.timeout = port, baud, 0.02
        s.dtr = s.rts = False
        s.open()
        r = esp32.Radio(s)
        try:
            r.send(esp32.CMD_CHANNEL, bytes([13]))
            info = r.request(esp32.CMD_HELLO, b"", esp32.MSG_INFO, timeout=hello_timeout)
            r.request(esp32.CMD_CHANNEL, bytes([13]), esp32.MSG_RESULT, timeout=5)
            if baud != 115200:
                r.request(esp32.CMD_BAUD, struct.pack("<I", 115200), esp32.MSG_RESULT, timeout=5)
            text = esp32.Info.parse(info).text
            break
        except esp32.RadioError:
            continue
        finally:
            r.close()
    elapsed = time.time() - started
    print(f"[quiet] {'ok' if text is not None else 'FALHOU'} em {elapsed:.1f}s", flush=True)
    if text is not None:
        sleep(0.5)
    return text


def quiet(port: str, *, serial_factory=None, attempts=ATTEMPTS, sleep=time.sleep) -> bool:
    return quiet_info(port, serial_factory=serial_factory, attempts=attempts, sleep=sleep) is not None
