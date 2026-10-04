"""Serial CDC-ACM pelo android.hardware.usb (pyjnius). Mesma interface do UsbCdcSerial do spike."""
import os
import struct
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

    def read(self, size=4096, timeout_ms=20):
        # Um pacote por bulkTransfer: no Android, um bulkTransfer maior que estoura o prazo
        # descarta o que já chegou (o BENCH perdia tudo com 4096 B / 20 ms a 921600).
        mps = self.ep_in.getMaxPacketSize()
        buf = bytearray(mps)
        out = bytearray()
        wait = max(1, int(timeout_ms))
        while len(out) + mps <= max(size, mps):
            n = self.conn.bulkTransfer(self.ep_in, buf, mps, wait)
            if n <= 0:
                break
            out += buf[:n]
            if n < mps:
                break
            wait = 1
        return bytes(out)

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
        try:
            self.conn.close()
        except Exception:
            pass
