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
