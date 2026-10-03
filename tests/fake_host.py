"""Imita um host: imprime o roteiro passado em argv e sai com o código dado.

    python tests/fake_host.py EXIT_CODE 'linha 1' 'sleep:0.2' 'linha 2' ...

Com DISTRIB_MANAGED_RUN=1, fechar o stdin vira KeyboardInterrupt (como no runner): imprime
"interrompido" e sai com 130. O item "deaf" desliga isso, para testar o terminate.
"""
import os
import signal
import sys
import threading
import time

code, *script = sys.argv[1:]
deaf = "deaf" in script
script = [item for item in script if item != "deaf"]


def _watch_stdin():
    sys.stdin.read()
    signal.raise_signal(signal.SIGINT)


if os.environ.get("DISTRIB_MANAGED_RUN") and sys.stdin is not None and not deaf:
    threading.Thread(target=_watch_stdin, daemon=True).start()
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
