from distrib import __main__ as cli


def test_checar_prints_and_returns_code(monkeypatch, capsys):
    from distrib import radio
    from distrib.radio import Check
    monkeypatch.setattr(radio, "run_checks", lambda cfg, catalogs: [
        Check("Placa", False, "Plugue a placa"), Check("prod.keys", True, "encontrado")])
    assert cli.main(["checar"]) == 1
    out = capsys.readouterr().out
    assert "✗ Placa: Plugue a placa" in out and "✓ prod.keys" in out


def test_atualizar_catalogo_calls_download(monkeypatch):
    from distrib import download
    seen = {}
    monkeypatch.setattr(download, "update_catalogs",
                        lambda cfg, games, **kw: seen.setdefault("games", games) and {})
    assert cli.main(["atualizar-catalogo", "frlg"]) == 0
    assert seen["games"] == ("frlg",)
