
from distrib.runners import selfcheck


def test_selfcheck_passa_com_o_pkhex_executavel(monkeypatch, tmp_path, capsys):
    pkhex = tmp_path / "pkhex"
    pkhex.write_bytes(b"")
    monkeypatch.setenv("POKELDN_PKHEX", str(pkhex))
    monkeypatch.setattr(selfcheck.os, "access", lambda p, m: True)
    code = selfcheck.main([])
    out = capsys.readouterr()
    assert code == 0, out.err
    assert "selfcheck ok" in out.out


def test_selfcheck_falha_sem_pkhex(monkeypatch, capsys):
    monkeypatch.delenv("POKELDN_PKHEX", raising=False)
    monkeypatch.setattr(selfcheck, "IS_ANDROID", False)
    assert selfcheck.main([]) == 1
    assert "PKHeX" in capsys.readouterr().err
