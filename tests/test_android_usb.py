"""AndroidUsbSerial, o shim do pyserial e list_ports, sobre um _Java falso que simula a placa."""
import os
import queue
import struct
import sys
import types

import pytest
import serial
import serial.tools

from distrib.platform import android_usb as au


class Buf:
    def __init__(self, size):
        self.data, self.pos, self.limit = bytearray(size), 0, size

    def position(self):
        return self.pos

    def flip(self):
        self.limit, self.pos = self.pos, 0

    def clear(self):
        self.pos, self.limit = 0, len(self.data)

    def get(self, dst, off, n):
        dst[off:off + n] = self.data[self.pos:self.pos + n]
        self.pos += n

    def put(self, payload):
        self.data[self.pos:self.pos + len(payload)] = payload
        self.pos += len(payload)


class Req:
    def __init__(self, conn):
        self.conn, self.buf, self.closed = conn, None, False

    def initialize(self, conn, ep):
        return True

    def queue(self, buf):
        self.buf = buf
        self.conn.pending.append(self)
        return True

    def cancel(self):
        if self in self.conn.pending:
            self.conn.pending.remove(self)
            if self.conn.collects_cancelled:
                self.conn.done.put(self)

    def close(self):
        self.closed = True

    def hashCode(self):
        return id(self)


class Conn:
    """A "placa": responde HELLO e conta os bytes escritos."""

    def __init__(self, collects_cancelled=True):
        self.control, self.written, self.closed = [], bytearray(), False
        self.pending, self.done = [], queue.Queue()
        self.collects_cancelled = collects_cancelled

    def claimInterface(self, itf, force):
        return True

    def controlTransfer(self, req_type, req, value, index, buf, length, timeout):
        self.control.append((req_type, req, value, index, bytes(buf) if buf else b""))
        return length

    def bulkTransfer(self, ep, chunk, length, timeout):
        self.written += chunk[:length]
        if bytes(chunk[:length]) == b"HELLO":
            self.deliver(b"pokeldn-radio ok")
        return length

    def deliver(self, payload):
        req = self.pending.pop(0)
        req.buf.put(payload)
        self.done.put(req)

    def requestWait(self, timeout):
        try:
            return self.done.get(timeout=timeout / 1000)
        except queue.Empty:
            raise TimeoutError("nada chegou") from None

    def close(self):
        self.closed = True


class Endpoint:
    def __init__(self, direction):
        self.direction = direction

    def getType(self):
        return au.USB_ENDPOINT_XFER_BULK

    def getDirection(self):
        return self.direction


class Interface:
    def __init__(self, id_, cls, eps=()):
        self.id_, self.cls, self.eps = id_, cls, eps

    def getInterfaceClass(self):
        return self.cls

    def getId(self):
        return self.id_

    def getEndpointCount(self):
        return len(self.eps)

    def getEndpoint(self, j):
        return self.eps[j]


class Device:
    def __init__(self, name="/dev/bus/usb/001/002", vid=0x1A86, pid=0x55D4):
        self.name, self.vid, self.pid = name, vid, pid
        self.itfs = [Interface(0, au.CLASS_COMM),
                     Interface(1, au.CLASS_DATA, (Endpoint(au.USB_DIR_IN), Endpoint(0)))]

    def getDeviceName(self):
        return self.name

    def getVendorId(self):
        return self.vid

    def getProductId(self):
        return self.pid

    def getProductName(self):
        return "CH9102"

    def getInterfaceCount(self):
        return len(self.itfs)

    def getInterface(self, i):
        return self.itfs[i]


class DeviceList:
    def __init__(self, devs):
        self.devs = devs

    def values(self):
        return self

    def toArray(self):
        return list(self.devs)


class Manager:
    def __init__(self, devs, conn, has_permission=True):
        self.devs, self.conn, self.granted = devs, conn, has_permission
        self.asked = []

    def getDeviceList(self):
        return DeviceList(self.devs)

    def hasPermission(self, dev):
        return self.granted

    def openDevice(self, dev):
        return self.conn


class FakeJava:
    def __init__(self, devs=None, conn=None, has_permission=True):
        self.conn = conn or Conn()
        self.devs = devs if devs is not None else [Device()]
        self.mgr = Manager(self.devs, self.conn, has_permission)

    def usb_manager(self):
        return self.mgr

    def request_permission(self, mgr, dev):
        mgr.asked.append(dev)
        mgr.granted = True

    def new_request(self):
        return Req(self.conn)

    def allocate(self, size):
        return Buf(size)


@pytest.fixture
def java(monkeypatch):
    fake = FakeJava()
    monkeypatch.setattr(au, "_java", fake)
    monkeypatch.setattr(au, "_LEAKED", [])
    monkeypatch.setattr(serial, "Serial", serial.Serial)
    monkeypatch.setattr(serial, "serial_for_url", serial.serial_for_url)
    return fake


def test_abrir_configura_a_linha(java):
    dev = au.AndroidUsbSerial(baud=921600)
    dev.set_lines(True, True)
    assert java.conn.control[0] == (0x21, 0x20, 0, 0, struct.pack("<IBBB", 921600, 0, 0, 8))
    assert java.conn.control[1][:3] == (0x21, 0x22, 0)
    assert java.conn.control[2][:3] == (0x21, 0x22, 3)
    assert dev.comm_if == 0 and dev.data_if == 1
    dev.close()


def test_pede_permissao_quando_falta(monkeypatch):
    fake = FakeJava(has_permission=False)
    monkeypatch.setattr(au, "_java", fake)
    au.AndroidUsbSerial().close()
    assert fake.mgr.asked == [fake.devs[0]]


def test_sem_placa_explica(java):
    java.devs[:] = [Device(vid=0x1234)]
    with pytest.raises(RuntimeError, match="nenhuma placa USB"):
        au.AndroidUsbSerial()


def test_escreve_e_le_pelo_leitor_continuo(java):
    dev = au.AndroidUsbSerial()
    assert dev.write(b"HELLO") == 5
    assert dev.read(4096, 1000) == b"pokeldn-radio ok"
    assert dev.read(4096, 5) == b""
    assert bytes(java.conn.written) == b"HELLO"
    dev.close()
    assert java.conn.closed


def test_escrita_grande_conta_bytes(java):
    dev = au.AndroidUsbSerial()
    assert dev.write(b"x" * 40000) == 40000
    assert len(java.conn.written) == 40000
    dev.close()


def test_close_vaza_em_vez_de_fechar_se_nao_recolheu(monkeypatch):
    fake = FakeJava(conn=Conn(collects_cancelled=False))
    monkeypatch.setattr(au, "_java", fake)
    monkeypatch.setattr(au, "_LEAKED", [])
    dev = au.AndroidUsbSerial()
    clock = iter(x * 0.6 for x in range(1000))      # o prazo de 1 s do close estoura rápido
    monkeypatch.setattr(au.time, "time", lambda: next(clock))
    dev.close()
    assert not fake.conn.closed and len(au._LEAKED) == 1


def test_list_ports(java):
    java.devs[:] = [Device(), Device("/dev/bus/usb/001/009", vid=0x046D, pid=1)]
    ports = au.list_ports()
    assert [(p.device, p.vid, p.pid, p.description) for p in ports] == [
        ("usb:/dev/bus/usb/001/002", 0x1A86, 0x55D4, "CH9102")]


def test_radio_list_boards_aceita_as_portas(java):
    from distrib import radio
    boards = radio.list_boards(au.list_ports)
    assert [(b.device, b.bridge) for b in boards] == [("usb:/dev/bus/usb/001/002", "CH9102")]


def test_shim_serial_como_o_radio_usa(java):
    au.install_serial_shim()
    s = serial.Serial()
    s.port, s.baudrate, s.timeout, s.dtr, s.rts = "usb:/dev/bus/usb/001/002", 115200, 0.5, False, False
    s.open()
    assert s.is_open
    s.write(b"HELLO")
    assert s.read(4096) == b"pokeldn-radio ok"      # devolve o que houver, sem esperar os 4096
    s.baudrate = 921600
    assert java.conn.control[-1][4] == struct.pack("<IBBB", 921600, 0, 0, 8)
    s.close()
    assert not s.is_open and java.conn.closed


def test_shim_serial_for_url_bloqueia_como_o_pyserial(java):
    au.install_serial_shim()
    s = serial.serial_for_url("usb:/dev/bus/usb/001/002", do_not_open=True)
    assert s.port == "usb:/dev/bus/usb/001/002" and s.timeout is None and not s.is_open
    s.timeout = 1.0
    s.open()
    s.rts = True
    assert java.conn.control[-1][:3] == (0x21, 0x22, 2)     # RTS sem apagar o DTR
    s.dtr = True
    assert java.conn.control[-1][:3] == (0x21, 0x22, 3)
    java.conn.deliver(b"OH")
    java.conn.deliver(b"AI")
    assert s.read(4) == b"OHAI"                              # junta os pedaços até o tamanho pedido
    assert s.in_waiting == 0
    s.close()


def test_shim_porta_sem_nome_usa_o_primeiro_vid(java):
    au.install_serial_shim()
    s = serial.Serial()
    s.port = "usb"
    s.open()
    assert s._dev.dev is java.devs[0]
    s.close()


def test_prepare_esptool(tmp_path, monkeypatch):
    monkeypatch.setenv("ESPTOOL_CFGFILE", "")      # o monkeypatch restaura o valor original
    monkeypatch.setitem(sys.modules, "serial.tools.list_ports", types.ModuleType("serial.tools.list_ports"))
    monkeypatch.setattr(serial.tools, "list_ports", serial.tools.list_ports, raising=False)
    au.prepare_esptool(tmp_path)
    text = (tmp_path / "esptool.cfg").read_text(encoding="utf-8")
    assert os.environ["ESPTOOL_CFGFILE"] == str(tmp_path / "esptool.cfg")
    assert "custom_reset_sequence = D0|R1|W0.1|D1|R0|W0.5|D0" in text
    assert "custom_hard_reset_sequence = R1|W0.1|R0" in text
    assert sys.modules["serial.tools.list_ports"].comports() == []
