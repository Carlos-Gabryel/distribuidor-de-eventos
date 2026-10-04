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


def _install_serial_shim(esptool=False):
    import serial
    import serial_shim

    cls = serial_shim.EspUsbSerial if esptool else serial_shim.UsbSerial
    serial.Serial = cls
    serial.serial_for_url = lambda url, *a, **k: cls()


def _quiet(esp32):
    """Como o distrib/runners/quiet.py: acha a placa (921600 ou 115200) e a deixa a 115200."""
    import serial
    for baud, timeout in ((921600, 1.5), (115200, 5)):
        s = serial.Serial()
        s.baudrate, s.timeout = baud, 0.02
        s.open()
        r = esp32.Radio(s)
        try:
            r.request(esp32.CMD_HELLO, b"", esp32.MSG_INFO, timeout=timeout)
            if baud != 115200:
                r.request(esp32.CMD_BAUD, struct.pack("<I", 115200), esp32.MSG_RESULT, timeout=5)
            return baud
        except esp32.RadioError:
            pass
        finally:
            r.close()
    return "sem resposta"


def bench():
    import os
    os.environ.setdefault("POKELDN_RADIO", "esp32:usb")
    _install_serial_shim()
    from pokeldn.ldn import esp32
    quiet = _quiet(esp32)
    radio = esp32.Radio.open_serial("usb", fast_baud=921600)
    try:
        r = radio.bench(400_000)
    finally:
        close = getattr(radio, "close", None)
        if close:
            close()
    return ("BENCH (placa estava a %s): rate=%.1f KB/s missing=%s rejected=%s\n%s"
            % (quiet, r["rate"] / 1024, r["missing"], r["rejected"], r))


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


_RESET = "D0|R1|W0.1|D1|R0|W0.5|D0"  # ClassicReset do esptool (D=DTR, R=RTS; 1 = linha ativa)
_HARD = "R1|W0.1|R0"                  # HardReset


def _prepare_esptool():
    """Troca o pyserial pelo shim e força o reset clássico pela config oficial do esptool."""
    import os
    import sys
    import tempfile
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    cfg = os.path.join(tempfile.gettempdir(), "esptool.cfg")
    with open(cfg, "w") as f:
        f.write("\n".join(["[esptool]", "custom_reset_sequence = " + _RESET,
                           "custom_hard_reset_sequence = " + _HARD, ""]))
    os.environ["ESPTOOL_CFGFILE"] = cfg  # lido na importação de esptool.loader
    _install_serial_shim(esptool=True)
    import esptool
    return esptool


def chip():
    esptool = _prepare_esptool()
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        with esptool.detect_chip("usb", connect_attempts=2) as esp:
            info = ["chip: %s" % esp.CHIP_NAME, "MAC: %s" % esp.read_mac()]
            try:
                info.append("flash: %s" % esp.flash_id())
            except Exception as e:  # noqa: BLE001
                info.append("flash: ? (%s)" % e)
    return "\n".join(info) + "\n--- log ---\n" + buf.getvalue()[-1500:]


def gravar():
    esptool = _prepare_esptool()
    import io
    import os
    import sys
    from contextlib import redirect_stdout, redirect_stderr
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    from distrib.runners import flash
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        rc = flash.main(["usb", os.path.join(here, "firmware")])
    return "flash rc=%s\n%s" % (rc, buf.getvalue()[-3000:])
