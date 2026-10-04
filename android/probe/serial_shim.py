"""Substitutos do pyserial sobre AndroidUsbSerial: UsbSerial (esp32.Radio) e EspUsbSerial (esptool)."""
import time

from usb_android import AndroidUsbSerial


class UsbSerial:
    """O pedaço do pyserial que o esp32.Radio usa."""

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

    def open(self):
        self._dev = AndroidUsbSerial(baud=self._baud, dtr=self._dtr, rts=self._rts)
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

    def close(self):
        self.is_open = False
        if self._dev is not None:
            self._dev.close()
            self._dev = None


class EspUsbSerial(UsbSerial):
    blocking_read = True
