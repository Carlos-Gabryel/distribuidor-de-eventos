import io
import tarfile

from distrib import download
from distrib.games import frlg, swsh


def fake_tarball(gallery):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in gallery.rglob("*"):
            if path.is_file():
                tar.add(path, arcname="EventsGallery-master/" + path.relative_to(gallery).as_posix())
        extra = b"ignore me"
        info = tarfile.TarInfo("EventsGallery-master/Released/Gen 5/x.pgf")
        info.size = len(extra)
        tar.addfile(info, io.BytesIO(extra))
    buf.seek(0)
    return buf


def test_extract_only_wanted_prefixes(gallery, tmp_path):
    n = download.extract_gallery(fake_tarball(gallery), tmp_path,
                                 (swsh.SWSH_RAW, frlg.FRLG_RAW))
    assert n == 6
    assert (tmp_path / swsh.SWSH_RAW / "0106 SWSH - Item Poke Ball x100.wc8").exists()
    assert not (tmp_path / "Released" / "Gen 5").exists()


def test_extract_refuses_path_traversal(tmp_path):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo("EventsGallery-master/Released/Gen 3/../../../fora.pk3")
        info.size = 1
        tar.addfile(info, io.BytesIO(b"x"))
    buf.seek(0)
    assert download.extract_gallery(buf, tmp_path / "d", (frlg.FRLG_RAW,)) == 0
    assert not (tmp_path / "fora.pk3").exists()


def test_update_catalogs(gallery, cfg):
    catalogs = download.update_catalogs(cfg, ("swsh", "frlg"),
                                        opener=lambda url, timeout: fake_tarball(gallery),
                                        log=lambda *a: None)
    assert len(catalogs["swsh"].events) == 2
    assert len([e for e in catalogs["frlg"].events if e.kind == "pokemon"]) == 2
    assert (cfg.catalog_dir / "frlg" / "index.json").exists()
    assert not (cfg.catalog_dir / "_raw").exists()


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def release_opener(body, assets=True):
    import json

    def opener(req, timeout=None):
        url = req if isinstance(req, str) else req.full_url
        if "api.github.com" in url:
            listed = [{"name": "swsh_validated.json", "browser_download_url": "https://x/v.json",
                       "size": len(body)}] if assets else []
            return Resp(json.dumps({"tag_name": "v1.0.0", "assets": listed}).encode())
        if url == "https://x/v.json":
            return Resp(body)
        raise OSError("inesperado: " + url)
    return opener


def test_fetch_validated_baixa_para_o_data_dir(cfg):
    body = b'{"records": {}}'
    assert download.fetch_validated(cfg, release_opener(body), log=lambda *a: None)
    assert (cfg.data_dir / "swsh_validated.json").read_bytes() == body
    assert not list(cfg.data_dir.glob("*.part"))


def test_fetch_validated_mantem_o_atual_se_falhar(cfg):
    logs = []
    assert not download.fetch_validated(cfg, release_opener(b"nao e json"), log=logs.append)
    assert not download.fetch_validated(cfg, release_opener(b"{}", assets=False), log=logs.append)
    assert not (cfg.data_dir / "swsh_validated.json").exists() and len(logs) == 2

    def offline(*a, **k):
        raise OSError("sem rede")
    assert not download.fetch_validated(cfg, offline, log=logs.append)


def test_update_catalogs_no_android_baixa_o_json(gallery, cfg, monkeypatch):
    monkeypatch.setattr(download, "IS_ANDROID", True)
    api = release_opener(b'{"records": {}}')

    def opener(req, timeout=None):
        return fake_tarball(gallery) if req == download.GALLERY_URL else api(req, timeout)
    download.update_catalogs(cfg, ("swsh",), opener=opener, log=lambda *a: None)
    assert (cfg.data_dir / "swsh_validated.json").exists()
