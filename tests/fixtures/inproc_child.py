"""Filho de teste do inproc: 3 linhas; 'exit3' sai com 3, 'boom' levanta, 'quiet' sai logo;
sem argumento, espera até o KeyboardInterrupt."""
import sys
import time

print("a")
print("b")
print("c", flush=True)
mode = sys.argv[1] if len(sys.argv) > 1 else "loop"
if mode == "exit3":
    sys.exit(3)
if mode == "boom":
    raise RuntimeError("falhou")
if mode == "quiet":
    sys.exit(0)
try:
    while True:
        time.sleep(0.01)
except KeyboardInterrupt:
    print("parado", flush=True)
    sys.exit(0)
