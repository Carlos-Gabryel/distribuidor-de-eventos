"""Pré-valida o catálogo SwSh (.wc8) com o PKHeX no PC.

Uso: python build/prevalidate_swsh.py [CATALOG_DIR] [-o OUT]
Gera um JSON com o sha256 de cada registro e o veredito, para o celular
(que não roda PKHeX) aceitar só o que já foi aprovado.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

VERSAO = "v0.5.0"


def classify(rec, validate, error_type):
    """Decide um registro: {"ok": True} ou {"ok": False, "motivo": str}."""
    try:
        validate(rec)
    except error_type as e:
        return {"ok": False, "motivo": str(e)}
    return {"ok": True}


def main(argv=None):
    padrao = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Distribuidor", "catalog", "swsh")
    ap = argparse.ArgumentParser()
    ap.add_argument("catalog", nargs="?", default=padrao)
    ap.add_argument("-o", "--out", default=str(RAIZ / "android_spike" / "swsh_validated.json"))
    args = ap.parse_args(argv)

    from distrib.pokeldn_path import ensure_importable
    ensure_importable(RAIZ / "vendor" / "pokeldn")
    from pokeldn import gifts, pokemon
    from pokeldn.swsh.gift_file import record

    records, falhas = {}, {}
    try:
        for p in sorted(Path(args.catalog).glob("*.wc8"), key=lambda x: x.name):
            try:
                rec = bytes(record(gifts.load(str(p), game="swsh")))
            except Exception as e:  # OSError, ValueError, struct.error...
                falhas[p.name] = str(e)
                continue
            res = classify(rec, pokemon.SERVICE.validate_gift, pokemon.BuilderError)
            res["file"] = p.name
            records[hashlib.sha256(rec).hexdigest()] = res
    finally:
        pokemon.SERVICE.close()

    out = {"pokeldn": VERSAO, "records": records}
    if falhas:
        out["falhas_de_leitura"] = falhas
    Path(args.out).write_text(
        json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    ok = sum(1 for r in records.values() if r["ok"])
    print("%d ok, %d recusados, %d ilegíveis" % (ok, len(records) - ok, len(falhas)))


if __name__ == "__main__":
    main()
