import hashlib
import io
import json
import shutil

import pytest

from distrib import update

BODY = b"novo exe" * 100
SHA = hashlib.sha256(BODY).hexdigest()


@pytest.fixture(autouse=True)
def _windows(monkeypatch):
    monkeypatch.setattr(update, "IS_LINUX", False)       # os testes do Linux ligam de volta


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def api(assets):
    return lambda req, timeout: Resp(json.dumps({"tag_name": "v2.1.0", "assets": assets}).encode())


ASSET = {"name": "Distribuidor.exe", "browser_download_url": "https://x/D.exe",
         "size": len(BODY), "digest": f"sha256:{SHA}"}


def test_parse_version():
    assert update.parse_version("v2.1.0") == (2, 1, 0)
    assert update.parse_version("2.0") == (2, 0)
    with pytest.raises(update.UpdateError):
        update.parse_version("beta")


def test_latest_and_newer():
    rel = update.latest(opener=api([ASSET]))
    assert rel == update.Release("v2.1.0", (2, 1, 0), "https://x/D.exe", len(BODY), SHA)
    assert update.newer(rel, "2.0.0") and not update.newer(rel, "2.1.0")
    assert not update.newer(None, "2.0.0")
    assert update.latest(opener=api([])) is None
    with pytest.raises(update.UpdateError):
        update.latest(opener=api([{**ASSET, "digest": None}]))


def test_download_checks_size_and_hash(tmp_path):
    rel = update.Release("v2.1.0", (2, 1, 0), "https://x/D.exe", len(BODY), SHA)
    path = update.download(rel, tmp_path, opener=lambda req, timeout: Resp(BODY))
    assert path.read_bytes() == BODY and path.name == "Distribuidor-v2.1.0.exe"
    bad = update.Release("v2.1.0", (2, 1, 0), "https://x/D.exe", len(BODY), "0" * 64)
    with pytest.raises(update.UpdateError):
        update.download(bad, tmp_path, opener=lambda req, timeout: Resp(BODY))
    assert not (tmp_path / "Distribuidor.exe.part").exists()


def test_apply_swaps_and_relaunches(tmp_path):
    exe = tmp_path / "Distribuidor.exe"
    exe.write_bytes(b"velho")
    new = tmp_path / "novo.exe"
    new.write_bytes(b"novo")
    launched = []
    update.apply(new, exe, launch=lambda argv, **kw: launched.append(argv))
    assert exe.read_bytes() == b"novo"
    assert (tmp_path / "Distribuidor.exe.old").read_bytes() == b"velho"
    assert launched == [[str(exe)]]
    update.cleanup(exe)
    assert not (tmp_path / "Distribuidor.exe.old").exists()


def test_apply_rolls_back_when_the_move_fails(tmp_path, monkeypatch):
    exe = tmp_path / "Distribuidor.exe"
    exe.write_bytes(b"velho")
    new = tmp_path / "novo.exe"
    new.write_bytes(b"novo")

    def boom(*a, **k):
        raise PermissionError("sem permissão")

    monkeypatch.setattr(shutil, "move", boom)
    with pytest.raises(OSError):
        update.apply(new, exe, launch=lambda argv, **kw: None)
    assert exe.read_bytes() == b"velho"


def test_asset_name_por_plataforma(monkeypatch):
    assert update.asset_name() == "Distribuidor.exe"
    monkeypatch.setattr(update, "IS_ANDROID", True)
    assert update.asset_name() == "Distribuidor.apk"


def test_latest_no_android_acha_o_apk_sem_sha_e_traz_o_html_url(monkeypatch):
    monkeypatch.setattr(update, "IS_ANDROID", True)
    apk = {"name": "Distribuidor.apk", "browser_download_url": "https://x/D.apk", "size": 5}
    opener = lambda req, timeout: Resp(json.dumps(
        {"tag_name": "v2.1.0", "html_url": "https://github.com/x/releases/v2.1.0", "assets": [apk]}).encode())
    rel = update.latest(opener=opener)
    assert rel.html_url == "https://github.com/x/releases/v2.1.0" and rel.url == "https://x/D.apk"


def test_find_asset():
    other = {"name": "swsh_validated.json", "browser_download_url": "https://x/v.json", "size": 2}
    assert update.find_asset("swsh_validated.json", opener=api([ASSET, other])) == "https://x/v.json"
    assert update.find_asset("nada", opener=api([ASSET])) is None


APPIMAGE = {**ASSET, "name": "Distribuidor-x86_64.AppImage", "browser_download_url": "https://x/D.AppImage"}


def test_linux_escolhe_o_appimage(monkeypatch):
    monkeypatch.setattr(update, "IS_LINUX", True)
    assert update.asset_name() == "Distribuidor-x86_64.AppImage"
    rel = update.latest(opener=api([ASSET, APPIMAGE]))
    assert rel.url == "https://x/D.AppImage"


def test_linux_fora_do_appimage_so_avisa(monkeypatch):
    monkeypatch.setattr(update, "IS_LINUX", True)
    monkeypatch.delenv("APPIMAGE", raising=False)
    assert update.appimage() is None and update.notify_only()
    rel = update.latest(opener=api([{**APPIMAGE, "digest": None}]))     # sem SHA-256: não baixa, então vale
    assert rel is not None and rel.sha256 == ""


def test_linux_no_appimage_baixa_ao_lado_e_troca(monkeypatch, tmp_path):
    monkeypatch.setattr(update, "IS_LINUX", True)
    image = tmp_path / "Distribuidor-x86_64.AppImage"
    image.write_bytes(b"velho")
    monkeypatch.setenv("APPIMAGE", str(image))
    assert update.appimage() == image and not update.notify_only()
    assert update.download_dir(tmp_path / "dados") == tmp_path
    rel = update.latest(opener=api([APPIMAGE]))
    new = update.download(rel, update.download_dir(tmp_path / "dados"), opener=lambda req, timeout: Resp(BODY))
    assert new.name == "Distribuidor-v2.1.0.AppImage" and new.read_bytes() == BODY
    launched = []
    update.apply(new, image, launch=lambda argv, **kw: launched.append(argv))
    assert image.read_bytes() == BODY and not new.exists()
    assert image.stat().st_mode & 0o777 == 0o755
    assert launched == [[str(image)]]
    update.cleanup(image)       # sem .old no Linux: não faz nada


def test_linux_download_que_nao_confere_nao_deixa_lixo(monkeypatch, tmp_path):
    monkeypatch.setattr(update, "IS_LINUX", True)
    bad = update.Release("v2.1.0", (2, 1, 0), "https://x/D.AppImage", len(BODY), "0" * 64)
    with pytest.raises(update.UpdateError):
        update.download(bad, tmp_path, opener=lambda req, timeout: Resp(BODY))
    assert list(tmp_path.iterdir()) == []
