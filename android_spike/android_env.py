"""Ambiente comum dos launchers Android (Termux, sem root). Importar antes de tudo e chamar prepare().

Prepara o pokeldn v0.5.0 (em ~/pokeldn ou $POKELDN_DIR) com:
- serial.Serial trocado por uma serial CDC-ACM sobre o fd do termux-usb (hello_usb.UsbCdcSerial);
- camada L2 userspace (o padrão no Linux é tap, que exige root);
- validação PKHeX trocada só pela checagem de selo do .wc8. No spike o .wc8 é oficial (Events
  Gallery) e já foi validado no PC; no app, isso vira o catálogo pré-validado (passo 3).
Antes do host, aquieta a placa como o distrib/runners/quiet.py (canal 13, HELLO, canal 13).
"""
import os
import runpy
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FD = int(sys.argv.pop())  # o termux-usb acrescenta o fd como último argumento
POKELDN = os.path.expanduser(os.environ.get("POKELDN_DIR", "~/pokeldn"))

os.environ["POKELDN_RADIO"] = "esp32:usbfd"
os.environ.setdefault("POKELDN_L2", "userspace")
os.environ.setdefault("PYTHONUNBUFFERED", "1")
sys.path[:0] = [HERE, os.path.dirname(HERE), POKELDN, os.path.join(POKELDN, "vendor", "LDN"), os.path.join(POKELDN, "bin")]
os.chdir(POKELDN)

import serial  # noqa: E402
from hello_usb import UsbCdcSerial  # noqa: E402

_device = None


class FdSerial:
    """O pedaço do pyserial que o esp32.Radio usa, sobre o único fd USB do processo."""

    def __init__(self, *args, **kwargs):
        self.port, self._baud, self.timeout, self.dtr, self.rts = None, 115200, 0.02, False, False
        self.is_open = False

    @property
    def baudrate(self):
        return self._baud

    @baudrate.setter
    def baudrate(self, value):
        self._baud = value
        if self.is_open:
            _device.set_baud(value)

    def open(self):
        global _device
        if _device is None:
            _device = UsbCdcSerial(FD, self._baud)
        else:
            _device.set_baud(self._baud)
        self.is_open = True

    def read(self, size=1):
        return _device.read(min(size, 4096), max(1, int((self.timeout or 0.02) * 1000)))

    def write(self, data):
        return _device.write(bytes(data))

    def flush(self):
        pass

    def reset_input_buffer(self):
        while _device.read(4096, 5):
            pass

    def close(self):
        self.is_open = False  # o fd e a libusb ficam abertos para o próximo open


serial.Serial = FdSerial

from pokeldn import pokemon  # noqa: E402
from pokeldn.ldn import esp32  # noqa: E402
from pokeldn.swsh import wc8  # noqa: E402
import validated_index  # noqa: E402


_INDEX = None


def _indice():
    """Carrega (uma vez) o catálogo pré-validado; None se o JSON não existir."""
    global _INDEX
    if _INDEX is None:
        caminho = os.path.join(HERE, "swsh_validated.json")
        _INDEX = validated_index.carregar(caminho) if os.path.exists(caminho) else False
    return _INDEX or None


def _validate_offline(data):
    if not wc8.sealed(data):
        raise pokemon.BuilderError("The WC8 size or checksum is invalid.")
    idx = _indice()
    if idx is None:
        print("[android] PKHeX pulado: só o selo do .wc8 foi conferido", flush=True)
        return
    ok, msg = validated_index.lookup(idx, data)
    if not ok:
        raise pokemon.BuilderError(msg)
    print("[android] aprovado pelo PKHeX no PC: %s" % msg, flush=True)


pokemon.SERVICE.validate_gift = _validate_offline


def attempt(baud, hello_timeout):
    s = serial.Serial()
    s.baudrate, s.timeout = baud, 0.02
    s.open()
    r = esp32.Radio(s)
    try:
        r.send(esp32.CMD_CHANNEL, bytes([13]))
        r.request(esp32.CMD_HELLO, b"", esp32.MSG_INFO, timeout=hello_timeout)
        r.request(esp32.CMD_CHANNEL, bytes([13]), esp32.MSG_RESULT, timeout=5)
        if baud != 115200:
            r.request(esp32.CMD_BAUD, struct.pack("<I", 115200), esp32.MSG_RESULT, timeout=5)
        return True
    except esp32.RadioError:
        return False
    finally:
        r.close()



def prepare():
    """Aquieta a placa (921600 e depois 115200) antes do host."""
    t = time.time()
    ok = attempt(921600, 1.5) or attempt(115200, 60)
    print(f"[quiet] {'ok' if ok else 'FALHOU'} em {time.time() - t:.1f}s", flush=True)
    time.sleep(0.5)
    return ok
