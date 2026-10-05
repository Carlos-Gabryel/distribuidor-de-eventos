"""Ambiente do app no Android: o que o pokeldn e o esptool precisam para rodar dentro do processo.

`apply(cfg)` é idempotente e só age no Android; chamado no início do app e no `runner.child`.
"""
from __future__ import annotations

import os
import sys

from distrib import validated_index
from distrib.platform import IS_ANDROID, android_usb
from distrib.pokeldn_path import ensure_importable

_applied = False


def _exit(code=None):
    raise SystemExit(code)


def restore_sys_exit() -> None:
    """O template Android do Flet troca `sys.exit` por `flet_exit`, que FECHA O APP. O click do
    esptool, o argparse do pokeldn e os nossos runners chamam `sys.exit` dentro de threads do
    próprio app, então `sys.exit` volta a só lançar SystemExit (que a thread do job absorve)."""
    if sys.exit is not _exit:
        sys.exit = _exit


def _validator(cfg, pokemon, wc8):
    """Troca do `validate_gift` (PKHeX, que não roda no celular): selo do .wc8 + o catálogo
    pré-validado pelo PKHeX no PC (o baixado em `cfg.data_dir` ou o embutido)."""
    def validate_offline(data):
        if not wc8.sealed(data):
            raise pokemon.BuilderError("The WC8 size or checksum is invalid.")
        index = validated_index.achar(cfg.data_dir)
        if index is None:
            print("[android] PKHeX pulado: só o selo do .wc8 foi conferido", flush=True)
            return
        ok, msg = validated_index.lookup(index, data)
        if not ok:
            raise pokemon.BuilderError(msg)
        print("[android] aprovado pelo PKHeX no PC: %s" % msg, flush=True)
    return validate_offline


def apply(cfg) -> None:
    global _applied
    if not IS_ANDROID:
        return
    restore_sys_exit()
    if _applied:
        return
    os.environ["POKELDN_L2"] = "userspace"           # o padrão no Linux é tap, que exige root
    os.chdir(cfg.pokeldn_dir)                        # os hosts usam caminhos relativos ao pokeldn
    ensure_importable(cfg.pokeldn_dir)
    android_usb.prepare_esptool(cfg.data_dir)        # antes de qualquer import do esptool
    android_usb.install_serial_shim()
    from pokeldn import pokemon
    from pokeldn.swsh import wc8
    pokemon.SERVICE.validate_gift = _validator(cfg, pokemon, wc8)
    _applied = True


def keep_screen_on(on: bool) -> None:
    """Liga/desliga FLAG_KEEP_SCREEN_ON. No desktop não faz nada."""
    if not IS_ANDROID:
        return
    try:
        android_usb.get_java().set_keep_screen_on(bool(on))
    except Exception as exc:  # noqa: BLE001 - a distribuição segue mesmo sem isso
        print(f"[android] keep_screen_on falhou: {exc}", flush=True)
