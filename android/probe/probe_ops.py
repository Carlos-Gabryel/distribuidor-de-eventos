"""Operações do probe (rodam numa thread; devolvem texto)."""
import struct
import time
import zlib

CMD_HELLO, MSG_INFO, MSG_CREDIT = 0x01, 0x81, 0x8B


def _cobs_encode(data):
    out, block = bytearray(), bytearray()
    for b in data:
        if b == 0:
            out += bytes([len(block) + 1]) + block
            block.clear()
        else:
            block.append(b)
            if len(block) == 254:
                out += b"\xff" + block
                block.clear()
    return bytes(out + bytes([len(block) + 1]) + block)


def _cobs_decode(data):
    out, i = bytearray(), 0
    while i < len(data):
        code = data[i]
        out += data[i + 1:i + code]
        i += code
        if code < 0xFF and i < len(data):
            out.append(0)
    return bytes(out)


def _frame(msg_type, payload=b""):
    body = bytes([msg_type]) + payload
    return _cobs_encode(body + struct.pack("<I", zlib.crc32(body))) + b"\x00"


def _parse(raw):
    body = _cobs_decode(raw)
    if len(body) < 5 or struct.unpack("<I", body[-4:])[0] != zlib.crc32(body[:-4]):
        return None
    return body[0], body[1:-4]


def hello():
    import usb_android
    from usb_android import AndroidUsbSerial
    s = AndroidUsbSerial(baud=115200)
    log = ["context: %s" % usb_android.ctx_source,
           "porta aberta (%04x:%04x, ctrl-if %s, data-if %s)"
           % (s.dev.getVendorId(), s.dev.getProductId(), s.comm_if, s.data_if)]
    try:
        for baud in (115200, 921600):
            s.set_baud(baud)
            pending, credits = b"", 0
            for attempt in range(1, 4):
                s.write(b"\x00" + _frame(CMD_HELLO))
                end = time.monotonic() + 1.0
                while time.monotonic() < end:
                    pending += s.read(4096, 100)
                    *frames, pending = pending.split(b"\x00")
                    for f in frames:
                        msg = _parse(f) if f else None
                        if msg is None:
                            continue
                        kind, payload = msg
                        if kind == MSG_CREDIT:
                            credits += 1
                        elif kind == MSG_INFO:
                            text = bytes(c for c in payload if 32 <= c < 127).decode()
                            log.append("HELLO ok a %d, tentativa %d: %s" % (baud, attempt, text))
                            return "\n".join(log)
            log.append("sem MSG_INFO a %d (%d CREDIT)" % (baud, credits))
    finally:
        s.close()
    log.append("FALHOU: a placa não respondeu ao HELLO")
    return "\n".join(log)


def _install_serial_shim():
    import serial
    from usb_android import AndroidUsbSerial

    class UsbSerial:
        """O pedaço do pyserial que o esp32.Radio usa, sobre AndroidUsbSerial."""

        def __init__(self, *a, **k):
            self.port, self._baud, self.timeout, self.dtr, self.rts = None, 115200, 0.02, False, False
            self.is_open = False
            self._dev = None

        @property
        def baudrate(self):
            return self._baud

        @baudrate.setter
        def baudrate(self, v):
            self._baud = v
            if self.is_open:
                self._dev.set_baud(v)

        def open(self):
            self._dev = AndroidUsbSerial(baud=self._baud, dtr=self.dtr, rts=self.rts)
            self.is_open = True

        def read(self, size=1):
            return self._dev.read(min(size, 4096), max(1, int((self.timeout or 0.02) * 1000)))

        def write(self, data):
            return self._dev.write(bytes(data))

        def flush(self):
            pass

        def reset_input_buffer(self):
            while self._dev.read(4096, 5):
                pass

        def close(self):
            self.is_open = False
            if self._dev is not None:
                self._dev.close()
                self._dev = None

    serial.Serial = UsbSerial


def bench():
    import os
    os.environ.setdefault("POKELDN_RADIO", "esp32:usb")
    _install_serial_shim()
    from pokeldn.ldn import esp32
    radio = esp32.Radio.open_serial("usb", fast_baud=921600)
    try:
        r = radio.bench(400_000)
    finally:
        close = getattr(radio, "close", None)
        if close:
            close()
    return ("BENCH: rate=%.1f KB/s missing=%s rejected=%s\n%s"
            % (r["rate"] / 1024, r["missing"], r["rejected"], r))


def unicorn_test():
    from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
    from unicorn.arm_const import UC_ARM_REG_R0
    import unicorn
    mu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    mu.mem_map(0x1000, 0x1000)
    code = bytes.fromhex("2a00a0e3")  # mov r0, #42
    mu.mem_write(0x1000, code)
    mu.emu_start(0x1000, 0x1000 + len(code))
    return "unicorn %s: r0=%d" % (unicorn.__version__, mu.reg_read(UC_ARM_REG_R0))
