"""Serial CDC-ACM pelo android.hardware.usb (pyjnius). Mesma interface do UsbCdcSerial do spike."""
import os
import struct
import threading
import time

VIDS = {0x1A86, 0x10C4, 0x0403, 0x303A}
ACTION = "dev.distrib.USB_PERMISSION"
FLAG_IMMUTABLE = 0x04000000
USB_ENDPOINT_XFER_BULK = 2
USB_DIR_IN = 0x80
CLASS_COMM, CLASS_DATA = 0x02, 0x0A


_ctx = None
ctx_source = None


def activity():
    """Context do app. Em thread de trabalho o pyjnius só enxerga classes do sistema
    (ClassNotFoundException na Activity do Flet), então cai para ActivityThread."""
    global _ctx, ctx_source
    if _ctx is not None:
        return _ctx
    from jnius import autoclass
    erros = []
    name = os.getenv("MAIN_ACTIVITY_HOST_CLASS_NAME")
    if name:
        try:
            _ctx, ctx_source = autoclass(name).mActivity, name
        except Exception as e:  # noqa: BLE001
            erros.append("%s: %s" % (name, e))
    if _ctx is None:
        app = autoclass("android.app.ActivityThread").currentApplication()
        if app is None:
            raise RuntimeError("sem Context do app; " + "; ".join(erros))
        _ctx, ctx_source = app, "ActivityThread.currentApplication"
    return _ctx


class AndroidUsbSerial:
    def __init__(self, device_name=None, baud=115200, perm_timeout=30.0, dtr=False, rts=False):
        from jnius import autoclass
        ctx = activity()
        self._mgr = ctx.getSystemService("usb")
        dev = self._pick(device_name)
        if not self._mgr.hasPermission(dev):
            Intent = autoclass("android.content.Intent")
            PendingIntent = autoclass("android.app.PendingIntent")
            intent = Intent(ACTION)
            intent.setPackage(ctx.getPackageName())
            pi = PendingIntent.getBroadcast(ctx, 0, intent, FLAG_IMMUTABLE)
            self._mgr.requestPermission(dev, pi)
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
        from jnius import autoclass
        UsbRequest = autoclass("android.hardware.usb.UsbRequest")
        ByteBuffer = autoclass("java.nio.ByteBuffer")
        self._rx, self._rx_cv, self._rx_err = bytearray(), threading.Condition(), None
        self._reqs = {}
        for _ in range(n_reqs):
            req = UsbRequest()
            if not req.initialize(self.conn, self.ep_in):
                raise RuntimeError("UsbRequest.initialize falhou")
            buf = ByteBuffer.allocate(size)
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
        for req, _, _ in getattr(self, "_reqs", {}).values():
            try:
                req.cancel()
            except Exception:
                pass
        try:
            self.conn.close()
        except Exception:
            pass
