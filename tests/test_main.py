from distrib import __main__ as cli


def test_atualizar_catalogo_calls_download(monkeypatch):
    from distrib import download
    seen = {}
    monkeypatch.setattr(download, "update_catalogs",
                        lambda cfg, games, **kw: seen.setdefault("games", games) and {})
    assert cli.main(["atualizar-catalogo", "frlg"]) == 0
    assert seen["games"] == ("frlg",)
