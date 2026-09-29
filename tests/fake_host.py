"""Imita um host: imprime o roteiro passado em argv e sai com o código dado.

    python tests/fake_host.py EXIT_CODE 'linha 1' 'sleep:0.2' 'linha 2' ...

Com SIGINT (Ctrl+C), imprime "interrompido" e sai com 130, como os hosts do pokeldn.
"""
import sys
import time

code, *script = sys.argv[1:]
try:
    for item in script:
        if item.startswith("sleep:"):
            time.sleep(float(item[6:]))
        else:
            print(item, flush=True)
except KeyboardInterrupt:
    print("interrompido", flush=True)
    sys.exit(130)
sys.exit(int(code))
