import hashlib
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "build"))
sys.path.insert(0, os.path.join(RAIZ, "android_spike"))

from prevalidate_swsh import classify  # noqa: E402
from validated_index import lookup  # noqa: E402


class Erro(Exception):
    pass


def test_classify_ok():
    assert classify(b"x", lambda r: {}, Erro) == {"ok": True}


def test_classify_recusado():
    def v(_):
        raise Erro("ruim")
    assert classify(b"x", v, Erro) == {"ok": False, "motivo": "ruim"}


def _idx(data, **ent):
    return {"records": {hashlib.sha256(data).hexdigest(): ent}}


def test_lookup_ok():
    ok, msg = lookup(_idx(b"abc", file="a.wc8", ok=True), b"abc")
    assert ok and msg == "a.wc8"


def test_lookup_recusado_com_motivo():
    ok, msg = lookup(_idx(b"abc", file="a.wc8", ok=False, motivo="xyz"), b"abc")
    assert not ok and "xyz" in msg


def test_lookup_ausente():
    ok, _ = lookup(_idx(b"abc", file="a", ok=True), b"outro")
    assert not ok
