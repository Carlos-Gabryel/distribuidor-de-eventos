"""Usado pelos testes do runner: imprime os argumentos; 'wait' espera até ser interrompido."""
import sys
import time

code, *words = sys.argv[1:]
print("args", *words, flush=True)
try:
    if code == "wait":
        time.sleep(30)
except KeyboardInterrupt:
    print("interrompido", flush=True)
    sys.exit(130)
sys.exit(0 if code == "wait" else int(code))
