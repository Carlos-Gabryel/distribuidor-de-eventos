"""Serial USB no Android (sem root): AndroidUsbSerial sobre android.hardware.usb via pyjnius,
o shim que troca o pyserial (Radio do pokeldn e esptool) e a listagem de placas.

Aprovado no celular na Fase 0 (A2/A4). O pyjnius fica atrás de `_Java`, que os testes trocam
por um fake (`use_java`). Leitura: sempre por UsbRequest contínuo; `bulkTransfer` com prazo
descarta o parcial e perde dados a 921600.
"""
from __future__ import annotations

import os
import struct
import threading
import time
import types
from dataclasses import dataclass

VIDS = {0x1A86, 0x10C4, 0x0403, 0x303A}
ACTION = "dev.distrib.USB_PERMISSION"
FLAG_IMMUTABLE = 0x04000000
FLAG_KEEP_SCREEN_ON = 0x00000080
USB_ENDPOINT_XFER_BULK = 2
USB_DIR_IN = 0x80
CLASS_COMM, CLASS_DATA = 0x02, 0x0A

_LEAKED = []  # conexões que não deu para fechar com segurança (ver AndroidUsbSerial.close)


class _Java:
    """Tudo que toca o pyjnius. Em thread de trabalho o pyjnius só enxerga classes do sistema
    (ClassNotFoundException na Activity do Flet), então o Context vem do ActivityThread."""

    def __init__(self):
        self._ctx = None
        self._activity = None

    def _autoclass(self, name):
        from jnius import autoclass
        return autoclass(name)

    def context(self):
        if self._ctx is None:
            app = self._autoclass("android.app.ActivityThread").currentApplication()
            if app is None:
                raise RuntimeError("sem Context do app")
            self._ctx = app
        return self._ctx

    def usb_manager(self):
        return self.context().getSystemService("usb")

    def request_permission(self, mgr, dev):
        ctx = self.context()
        intent = self._autoclass("android.content.Intent")(ACTION)
        intent.setPackage(ctx.getPackageName())
        pi = self._autoclass("android.app.PendingIntent").getBroadcast(ctx, 0, intent, FLAG_IMMUTABLE)
        mgr.requestPermission(dev, pi)

    def new_request(self):
        return self._autoclass("android.hardware.usb.UsbRequest")()

    def allocate(self, size):
        return self._autoclass("java.nio.ByteBuffer").allocate(size)

    def activity(self):
        """Activity do Flet. Só resolve na thread principal (ver `context`): `prime_activity()` a
        guarda no início do app."""
        if self._activity is None:
            self._activity = self._autoclass(os.environ["MAIN_ACTIVITY_HOST_CLASS_NAME"]).mActivity
        return self._activity

    prime_activity = activity

    def set_keep_screen_on(self, on):
        """FLAG_KEEP_SCREEN_ON na janela, executado na thread de UI do Android."""
        from jnius import PythonJavaClass, java_method
        activity = self.activity()

        class _Run(PythonJavaClass):
            __javainterfaces__ = ["java/lang/Runnable"]

            @java_method("()V")
            def run(self_):  # noqa: N805
                window = activity.getWindow()
                (window.addFlags if on else window.clearFlags)(FLAG_KEEP_SCREEN_ON)

        runnable = _Run()
        _KEEP.append(runnable)
        activity.runOnUiThread(runnable)
        del _KEEP[:-8]


_KEEP = []  # mantém vivos os Runnables até o ART executá-los
_java = _Java()


def use_java(java) -> None:
    """Troca a fachada (testes)."""
    global _java
    _java = java


def get_java():
    return _java


class AndroidUsbSerial:
    def __init__(self, device_name=None, baud=115200, perm_timeout=30.0, dtr=False, rts=False):
        self._java = _java
        self._mgr = self._java.usb_manager()
        dev = self._pick(device_name)
        if not self._mgr.hasPermission(dev):
            self._java.request_permission(self._mgr, dev)
            end = time.time() + perm_timeout
            while not self._mgr.hasPermission(dev) and time.time() < end:
                time.sleep(0.2)
            if not self._mgr.hasPermission(dev):
                raise RuntimeError("permissão USB negada ou não respondida em %ds" % perm_timeout)
        self.dev = dev
        self.conn = self._mgr.openDevice(dev)
        if self.conn is None:
            raise RuntimeError("openDevice devolveu null")
        self.comm_if, self.data_if = None, None
        self.ep_in, self.ep_out = None, None
        self._find_interfaces()
        self._start_reader()
        self.set_baud(baud)
        self.set_lines(dtr, rts)

    def _pick(self, device_name):
        devs = self._mgr.getDeviceList().values().toArray()
        found = [d for d in devs if (device_name and d.getDeviceName() == device_name)
                 or (not device_name and d.getVendorId() in VIDS)]
        if not found:
            seen = ", ".join("%04x:%04x" % (d.getVendorId(), d.getProductId()) for d in devs) or "nenhum"
            raise RuntimeError("nenhuma placa USB (VIDs %s); dispositivos vistos: %s"
                               % (", ".join("%04x" % v for v in sorted(VIDS)), seen))
        return found[0]

    def _find_interfaces(self):
        dev = self.dev
        comm, data = None, None
        for i in range(dev.getInterfaceCount()):
            itf = dev.getInterface(i)
            cls = itf.getInterfaceClass()
            if cls == CLASS_COMM and comm is None:
                comm = itf
            elif cls == CLASS_DATA and data is None:
                data = itf
        if data is None:
            raise RuntimeError("sem interface CDC-data (0x0A): adaptador USB-serial de fabricante, "
                               "não CDC-ACM (VID %04x)" % dev.getVendorId())
        for itf in (comm, data):
            if itf is not None and not self.conn.claimInterface(itf, True):
                raise RuntimeError("claimInterface falhou na interface %d" % itf.getId())
        self.comm_if = comm.getId() if comm is not None else 0
        self.data_if = data.getId()
        for j in range(data.getEndpointCount()):
            ep = data.getEndpoint(j)
            if ep.getType() != USB_ENDPOINT_XFER_BULK:
                continue
            if ep.getDirection() == USB_DIR_IN:
                self.ep_in = ep
            else:
                self.ep_out = ep
        if self.ep_in is None or self.ep_out is None:
            raise RuntimeError("endpoints bulk IN/OUT não encontrados")

    def _ctrl(self, req_type, req, value, data=b""):
        buf = bytearray(data) if data else None
        n = self.conn.controlTransfer(req_type, req, value, self.comm_if, buf, len(data) if data else 0, 1000)
        if n < 0:
            raise RuntimeError("controlTransfer 0x%02x falhou (%d)" % (req, n))

    def set_baud(self, baud):
        self.baud = baud
        self._ctrl(0x21, 0x20, 0, struct.pack("<IBBB", baud, 0, 0, 8))  # SET_LINE_CODING 8N1

    def set_lines(self, dtr, rts):
        self.dtr, self.rts = bool(dtr), bool(rts)
        self._ctrl(0x21, 0x22, int(self.dtr) | (int(self.rts) << 1))  # SET_CONTROL_LINE_STATE

    def _start_reader(self, n_reqs=4, size=16384):
        """Leitura contínua por UsbRequest (sem prazo, então nada é descartado). bulkTransfer
        com prazo perde o parcial, e um pacote por chamada não esvazia a placa a 921600."""
        self._rx, self._rx_cv, self._rx_err = bytearray(), threading.Condition(), None
        self._reqs = {}
        for _ in range(n_reqs):
            req = self._java.new_request()
            if not req.initialize(self.conn, self.ep_in):
                raise RuntimeError("UsbRequest.initialize falhou")
            buf = self._java.allocate(size)
            self._reqs[req.hashCode()] = (req, buf, bytearray(size))
            if not req.queue(buf):
                raise RuntimeError("UsbRequest.queue falhou")
        self._running = True
        self._reader = threading.Thread(target=self._reader_loop, name="usb-rx", daemon=True)
        self._reader.start()

    def _reader_loop(self):
        try:
            while self._running:
                try:
                    done = self.conn.requestWait(100)
                except Exception:  # noqa: BLE001 - TimeoutException do Java: nada chegou
                    continue
                if done is None:
                    break
                req, buf, tmp = self._reqs[done.hashCode()]
                n = buf.position()
                if n:
                    buf.flip()
                    buf.get(tmp, 0, n)
                    with self._rx_cv:
                        self._rx += tmp[:n]
                        self._rx_cv.notify_all()
                buf.clear()
                if self._running and not req.queue(buf):
                    raise RuntimeError("UsbRequest.queue falhou")
        except Exception as e:  # noqa: BLE001
            self._rx_err = e
        finally:
            with self._rx_cv:
                self._rx_cv.notify_all()

    def read(self, size=4096, timeout_ms=20):
        with self._rx_cv:
            if not self._rx and self._rx_err is None:
                self._rx_cv.wait(max(1, int(timeout_ms)) / 1000)
            if not self._rx and self._rx_err is not None:
                raise RuntimeError("leitura USB parou: %s" % self._rx_err)
            out = bytes(self._rx[:size])
            del self._rx[:size]
            return out

    def write(self, data):
        data = bytes(data)
        off = 0
        while off < len(data):
            chunk = bytearray(data[off:off + 16384])
            n = self.conn.bulkTransfer(self.ep_out, chunk, len(chunk), 2000)
            if n <= 0:
                raise RuntimeError("bulk write falhou (%d)" % n)
            off += n
        return len(data)

    def close(self):
        self._running = False
        reader = getattr(self, "_reader", None)
        if reader is not None:
            reader.join(1.0)
        # Cancelar, recolher cada UsbRequest pelo requestWait e só então fechá-las e fechar a
        # conexão. Request ainda na fila quando a conexão fecha derruba o app depois (finalizer).
        reqs = getattr(self, "_reqs", {})
        for req, _, _ in reqs.values():
            try:
                req.cancel()
            except Exception:
                pass
        pending, end = set(reqs), time.time() + 1.0
        while pending and time.time() < end:
            try:
                done = self.conn.requestWait(100)
            except Exception:  # noqa: BLE001 - TimeoutException
                continue
            if done is None:
                break
            pending.discard(done.hashCode())
        if not pending:
            for req, _, _ in reqs.values():
                try:
                    req.close()
                except Exception:
                    pass
        else:
            # Sem recolher todas, fechar a request ou a conexão é o que derruba o app:
            # deixa a conexão aberta e guarda tudo vivo (vaza, mas não crasha).
            _LEAKED.append((self.conn, reqs))
            return
        try:
            self.conn.close()
        except Exception:
            pass


# ---- listagem de placas ----
@dataclass(frozen=True)
class UsbPort:
    """O que `radio.list_boards` lê de um item de `serial.tools.list_ports.comports()`."""
    device: str
    vid: int
    pid: int
    description: str = ""


def list_ports() -> list[UsbPort]:
    """Placas USB-serial conhecidas (VIDS) que o Android enxerga; `device` = "usb:<deviceName>"."""
    out = []
    for d in _java.usb_manager().getDeviceList().values().toArray():
        if d.getVendorId() in VIDS:
            out.append(UsbPort("usb:" + d.getDeviceName(), d.getVendorId(), d.getProductId(),
                               d.getProductName() or ""))
    return out


# ---- substituto do pyserial ----
class UsbSerial:
    """O pedaço do pyserial que o esp32.Radio usa (`serial.Serial()`)."""

    blocking_read = False  # False: devolve o que houver (Radio); True: semântica do pyserial

    def __init__(self, *a, **k):
        self.port, self._baud, self.timeout, self._dtr, self._rts = None, 115200, 0.02, False, False
        self.write_timeout = None
        self.is_open = False
        self._dev = None

    @property
    def name(self):
        return self.port or "usb"

    @property
    def baudrate(self):
        return self._baud

    @baudrate.setter
    def baudrate(self, v):
        self._baud = v
        if self.is_open:
            self._dev.set_baud(v)

    def _lines(self):
        if self.is_open:
            self._dev.set_lines(self._dtr, self._rts)

    @property
    def dtr(self):
        return self._dtr

    @dtr.setter
    def dtr(self, v):
        self._dtr = bool(v)
        self._lines()

    @property
    def rts(self):
        return self._rts

    @rts.setter
    def rts(self, v):
        self._rts = bool(v)
        self._lines()

    def setDTR(self, v=True):
        self.dtr = v

    def setRTS(self, v=True):
        self.rts = v

    def _device_name(self):
        """`usb:<deviceName>` (de `list_ports`) escolhe a placa; qualquer outra coisa ("usb")
        deixa a escolha para o primeiro VID conhecido."""
        port = self.port or ""
        return port[4:] if port.startswith("usb:") and len(port) > 4 else None

    def open(self):
        self._dev = AndroidUsbSerial(self._device_name(), baud=self._baud, dtr=self._dtr, rts=self._rts)
        self.is_open = True

    @property
    def in_waiting(self):
        dev = self._dev
        if dev is None:
            return 0
        with dev._rx_cv:
            return len(dev._rx)

    inWaiting = in_waiting.fget

    def read(self, size=1):
        t = 3600.0 if self.timeout is None else self.timeout
        if not self.blocking_read:
            return self._dev.read(min(size, 4096), max(1, int((t or 0.02) * 1000)))
        end = time.monotonic() + t
        out = b""
        while len(out) < size:
            left = end - time.monotonic()
            out += self._dev.read(size - len(out), max(1, int(left * 1000)))
            if time.monotonic() >= end:
                break
        return out

    def write(self, data):
        return self._dev.write(bytes(data))

    def flush(self):
        pass

    def flushOutput(self):
        pass

    reset_output_buffer = flushOutput

    def reset_input_buffer(self):
        dev = self._dev
        if dev is not None:
            with dev._rx_cv:
                del dev._rx[:]

    flushInput = reset_input_buffer

    def isOpen(self):  # API antiga do pyserial, usada pelo reset do esptool
        return self.is_open

    def close(self):
        self.is_open = False
        if self._dev is not None:
            self._dev.close()
            self._dev = None


class EspUsbSerial(UsbSerial):
    """Para o esptool (`serial.serial_for_url`): `read` bloqueante, como o pyserial."""

    blocking_read = True

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        # Padrão do pyserial (o esptool restaura este valor depois de cada comando e espera o
        # OHAI do stub com ele; com 0,02 s desistia em 21 ms).
        self.timeout = k.get("timeout")


_RESET = "D0|R1|W0.1|D1|R0|W0.5|D0"  # ClassicReset do esptool (D=DTR, R=RTS; 1 = linha ativa)
_HARD = "R1|W0.1|R0"                  # HardReset


def install_serial_shim() -> None:
    """`serial.Serial()` (Radio) e `serial.serial_for_url()` (esptool) passam a usar o USB do Android.
    Idempotente."""
    import serial

    def serial_for_url(url, *a, **k):
        s = EspUsbSerial(**{x: k[x] for x in ("timeout",) if x in k})
        s.port = url  # o esptool lê .port (serial_port.startswith)
        return s

    serial.Serial = UsbSerial
    serial.serial_for_url = serial_for_url


def prepare_esptool(cfg_dir) -> None:
    """Antes de importar o esptool: reset clássico pela config oficial e `list_ports` vazio.

    No esptool o reset em Unix usa ioctl no fd; `custom_reset_sequence` tem prioridade e só usa
    DTR/RTS pelo shim. O arquivo é lido na importação de `esptool.loader`. O pyserial não tem
    `list_ports` para sys.platform "android" (ImportError no esp_pylib); a porta é sempre o shim.
    """
    import sys
    cfg_dir = os.fspath(cfg_dir)
    os.makedirs(cfg_dir, exist_ok=True)
    cfg = os.path.join(cfg_dir, "esptool.cfg")
    with open(cfg, "w", encoding="utf-8") as f:
        f.write("\n".join(["[esptool]", "custom_reset_sequence = " + _RESET,
                           "custom_hard_reset_sequence = " + _HARD, ""]))
    os.environ["ESPTOOL_CFGFILE"] = cfg
    mod = sys.modules.get("serial.tools.list_ports")
    if mod is None or not hasattr(mod, "comports"):
        import serial.tools
        stub = types.ModuleType("serial.tools.list_ports")
        stub.comports = lambda *a, **k: []
        stub.grep = lambda *a, **k: iter(())
        sys.modules["serial.tools.list_ports"] = stub
        serial.tools.list_ports = stub
