"""Índice dos .wc8 pré-validados pelo PKHeX no PC (sem efeitos colaterais)."""
import hashlib
import json


def carregar(caminho):
    """Lê o JSON gerado por build/prevalidate_swsh.py."""
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def lookup(index, data):
    """Retorna (aprovado, mensagem) para o registro `data` segundo `index`."""
    sha = hashlib.sha256(data).hexdigest()
    ent = index.get("records", {}).get(sha)
    if ent is None:
        return False, "Este .wc8 não está no catálogo validado pelo PKHeX no PC."
    if ent.get("ok"):
        return True, ent.get("file", "")
    return False, ("Este .wc8 não está no catálogo validado pelo PKHeX no PC. "
                   "Motivo: %s" % ent.get("motivo", "?"))
