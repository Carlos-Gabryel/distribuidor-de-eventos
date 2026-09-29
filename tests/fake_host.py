"""Imita um host: imprime o roteiro passado em argv e sai com o código dado.

    python tests/fake_host.py EXIT_CODE 'linha 1' 'sleep:0.2' 'linha 2' ...
"""
import sys
import time

code, *script = sys.argv[1:]
for item in script:
    if item.startswith("sleep:"):
        time.sleep(float(item[6:]))
    else:
        print(item, flush=True)
sys.exit(int(code))
