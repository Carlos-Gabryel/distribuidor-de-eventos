"""Prova de viabilidade Android: Mystery Gift de FireRed/LeafGreen pelo celular (Termux, sem root).

Uso (com o repo do distrib clonado em ~/distrib e o pokeldn em ~/pokeldn):
    termux-usb -r -e "python ~/distrib/android_spike/frlg_android.py --pk3 ARQUIVO.pk3 --keys ~/prod.keys" /dev/bus/usb/XXX/YYY

Uma sessão: entrega um .pk3 a um console e sai (0 entregue, 1 não entregue, 124 sem console).
Precisa do unicorn (pip install unicorn==2.1.4).
"""
import sys

import android_env

android_env.prepare()
from distrib.runners import frlg_session  # noqa: E402

sys.exit(frlg_session.main(["--pokeldn", android_env.POKELDN, *sys.argv[1:], "--phy", "auto"]))
