"""Teste da Task 2: aquieta a placa (115200, canal 13, fila vazia) e sobe o host do pokeldn."""
import runpy, struct, sys, time
sys.path[:0] = ['.', 'vendor/LDN', 'bin']
import serial
from pokeldn.ldn import esp32
PORT = 'COM4'


def attempt(baud, hello_timeout):
    s = serial.Serial(); s.port = PORT; s.baudrate = baud; s.timeout = 0.02; s.dtr = s.rts = False
    s.open()
    r = esp32.Radio(s)
    try:
        r.send(esp32.CMD_CHANNEL, bytes([13]))
        r.request(esp32.CMD_HELLO, b'', esp32.MSG_INFO, timeout=hello_timeout)
        r.request(esp32.CMD_CHANNEL, bytes([13]), esp32.MSG_RESULT, timeout=5)
        if baud != 115200:
            r.request(esp32.CMD_BAUD, struct.pack('<I', 115200), esp32.MSG_RESULT, timeout=5)
        return True
    except esp32.RadioError:
        return False
    finally:
        r.close()


t = time.time()
ok = attempt(921600, 1.5) or attempt(115200, 60)
print(f'[quiet] {"ok" if ok else "FALHOU"} em {time.time()-t:.1f}s', flush=True)
time.sleep(0.5)
sys.argv = ['bin/swsh_gift_host.py', *sys.argv[1:]]
runpy.run_path('bin/swsh_gift_host.py', run_name='__main__')
