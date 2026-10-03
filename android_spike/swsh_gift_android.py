"""Prova de viabilidade Android, passo 4: Mystery Gift de Sword/Shield pelo celular (Termux, sem root).

Uso:
    termux-usb -r -e "python swsh_gift_android.py --record ARQUIVO.wc8 --keys ~/prod.keys" /dev/bus/usb/XXX/YYY
"""
import runpy
import sys

import android_env

android_env.prepare()
sys.argv = ["bin/swsh_gift_host.py", "--seconds", "600", "--no-validate", *sys.argv[1:]]
runpy.run_path("bin/swsh_gift_host.py", run_name="__main__")
