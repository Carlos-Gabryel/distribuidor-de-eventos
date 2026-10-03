"""Prova de viabilidade Android, passo 2: HELLO na ESP32 pelo Termux, sem root.

Uso (no Termux, com a placa no OTG):
    termux-usb -r -e "python hello_usb.py" /dev/bus/usb/XXX/YYY

O termux-usb passa o file descriptor do USB como último argumento. A serial CDC-ACM é
feita direto na libusb (libusb_wrap_sys_device), com DTR/RTS desligados para não resetar a placa.
"""
import ctypes as C
import os
import struct
import sys
import time
import zlib

BAUD = 115200
CMD_HELLO, MSG_INFO, MSG_CREDIT = 0x01, 0x81, 0x8B


class UsbCdcSerial:
    """Serial CDC-ACM sobre um fd do Android. Interface mínima: write, read, close."""

    def __init__(self, fd: int, baud: int = BAUD):
        lib = C.CDLL(os.path.join(os.environ.get("PREFIX", "/data/data/com.termux/files/usr"),
                                  "lib", "libusb-1.0.so"))
        lib.libusb_wrap_sys_device.argtypes = [C.c_void_p, C.c_ssize_t, C.POINTER(C.c_void_p)]
        lib.libusb_control_transfer.argtypes = [C.c_void_p, C.c_uint8, C.c_uint8, C.c_uint16,
                                                C.c_uint16, C.c_char_p, C.c_uint16, C.c_uint]
        lib.libusb_bulk_transfer.argtypes = [C.c_void_p, C.c_uint8, C.c_char_p, C.c_int,
                                             C.POINTER(C.c_int), C.c_uint]
        lib.libusb_claim_interface.argtypes = [C.c_void_p, C.c_int]
        self.lib = lib
        lib.libusb_set_option(C.c_void_p(None), C.c_int(2))  # NO_DEVICE_DISCOVERY (Android)
        self.ctx = C.c_void_p()
        self._check(lib.libusb_init(C.byref(self.ctx)), "libusb_init")
        self.h = C.c_void_p()
        self._check(lib.libusb_wrap_sys_device(self.ctx, fd, C.byref(self.h)), "wrap_sys_device")
        self.comm_if, self.data_if, self.ep_in, self.ep_out = self._find_cdc()
        for i in (self.comm_if, self.data_if):
            lib.libusb_detach_kernel_driver(self.h, i)  # no Android costuma falhar; tanto faz
            self._check(lib.libusb_claim_interface(self.h, i), f"claim_interface {i}")
        self.set_baud(baud)
        self._check(self._ctrl(0x21, 0x22, 0, self.comm_if, b""), "SET_CONTROL_LINE_STATE")

    def set_baud(self, baud: int):
        line = struct.pack("<IBBB", baud, 0, 0, 8)  # 8N1
        self._check(self._ctrl(0x21, 0x20, 0, self.comm_if, line), "SET_LINE_CODING")

    @staticmethod
    def _check(rc, what):
        if rc < 0:
            raise OSError(f"{what} falhou: libusb {rc}")
        return rc

    def _ctrl(self, rtype, req, value, index, data):
        buf = C.create_string_buffer(bytes(data), max(len(data), 1))
        return self.lib.libusb_control_transfer(self.h, rtype, req, value, index, buf, len(data), 1000)

    def _find_cdc(self):
        buf = C.create_string_buffer(512)
        n = self._check(self.lib.libusb_control_transfer(self.h, 0x80, 6, 0x0200, 0, buf, 512, 1000),
                        "GET_DESCRIPTOR")
        raw, i = buf.raw[:n], 0
        comm_if = data_if = ep_in = ep_out = None
        cur_if = cur_cls = None
        while i + 1 < len(raw) and raw[i] > 0:
            length, dtype = raw[i], raw[i + 1]
            if dtype == 4:  # interface
                cur_if, cur_cls = raw[i + 2], raw[i + 5]
                if cur_cls == 0x02 and comm_if is None:
                    comm_if = cur_if
                if cur_cls == 0x0A and data_if is None:
                    data_if = cur_if
            elif dtype == 5 and cur_cls == 0x0A and cur_if == data_if and raw[i + 3] & 3 == 2:
                addr = raw[i + 2]
                if addr & 0x80:
                    ep_in = ep_in or addr
                else:
                    ep_out = ep_out or addr
            i += length
        print(f"descritor: comm_if={comm_if} data_if={data_if} "
              f"ep_in={ep_in and hex(ep_in)} ep_out={ep_out and hex(ep_out)}")
        if None in (comm_if, data_if, ep_in, ep_out):
            raise OSError("não achei as interfaces CDC-ACM; mande o descritor: " + raw.hex(" "))
        return comm_if, data_if, ep_in, ep_out

    def write(self, data: bytes) -> int:
        done = C.c_int()
        self._check(self.lib.libusb_bulk_transfer(self.h, self.ep_out, data, len(data),
                                                  C.byref(done), 1000), "bulk OUT")
        return done.value

    def read(self, size: int = 512, timeout_ms: int = 100) -> bytes:
        buf, got = C.create_string_buffer(size), C.c_int()
        rc = self.lib.libusb_bulk_transfer(self.h, self.ep_in, buf, size, C.byref(got), timeout_ms)
        if rc < 0 and rc != -7:  # -7 = timeout
            self._check(rc, "bulk IN")
        return buf.raw[:got.value]

    def close(self):
        for i in (self.comm_if, self.data_if):
            self.lib.libusb_release_interface(self.h, i)
        self.lib.libusb_close(self.h)
        self.lib.libusb_exit(self.ctx)


def cobs_encode(data: bytes) -> bytes:
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


def cobs_decode(data: bytes) -> bytes:
    out, i = bytearray(), 0
    while i < len(data):
        code = data[i]
        out += data[i + 1:i + code]
        i += code
        if code < 0xFF and i < len(data):
            out.append(0)
    return bytes(out)


def frame(msg_type: int, payload: bytes = b"") -> bytes:
    body = bytes([msg_type]) + payload
    return cobs_encode(body + struct.pack("<I", zlib.crc32(body))) + b"\x00"


def parse(raw: bytes):
    body = cobs_decode(raw)
    if len(body) < 5 or struct.unpack("<I", body[-4:])[0] != zlib.crc32(body[:-4]):
        return None
    return body[0], body[1:-4]


def main():
    fd = int(sys.argv[-1])
    s = UsbCdcSerial(fd)
    print("porta aberta a", BAUD)
    pending, credits = b"", 0
    for attempt in range(1, 6):
        s.write(b"\x00" + frame(CMD_HELLO))  # 0x00 antes descarta lixo pendente na placa
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            pending += s.read()
            *frames, pending = pending.split(b"\x00")
            for f in frames:
                msg = parse(f) if f else None
                if msg is None:
                    continue
                kind, payload = msg
                if kind == MSG_CREDIT:
                    credits += 1
                elif kind == MSG_INFO:
                    text = bytes(c for c in payload if 32 <= c < 127).decode()
                    print(f"HELLO ok na tentativa {attempt}: {text}")
                    print("payload:", payload.hex(" "))
                    s.close()
                    return 0
                else:
                    print(f"mensagem 0x{kind:02x}: {payload.hex(' ')}")
        print(f"tentativa {attempt}: sem MSG_INFO ({credits} CREDIT até agora)")
    s.close()
    print("FALHOU: a placa não respondeu ao HELLO")
    return 1


if __name__ == "__main__":
    sys.exit(main())
