import io

import pytest

from distrib import board, runner


def test_firmware_for(tmp_path):
    (tmp_path / "pokeldn-radio-s3.bin").write_bytes(b"x")
    assert board.firmware_for("ESP32-S3", tmp_path) == tmp_path / "pokeldn-radio-s3.bin"
    with pytest.raises(board.BoardError, match="não é suportado"):
        board.firmware_for("ESP8266", tmp_path)
    with pytest.raises(board.BoardError, match="Falta o firmware"):
        board.firmware_for("ESP32", tmp_path)


def test_parse_progress():
    assert board.parse_progress("Writing at 0x00010000 [=====>    ]  45.2% 1/2 bytes") == pytest.approx(0.452)
    assert board.parse_progress("Writing at 0x00010000... (100 %)") == 1.0
    assert board.parse_progress("Hash of data verified.") is None


class FakeProc:
    def __init__(self, lines, code):
        self.stdout = io.StringIO("".join(line + "\n" for line in lines))
        self.code = code

    def wait(self):
        return self.code


def test_flash_streams_lines_and_progress(cfg):
    seen = {}

    def popen(argv, **kw):
        seen["argv"] = argv
        return FakeProc(["[flash] chip ESP32", "Writing at 0x0 [=>  ] 50.0%", "[flash] ok"], 0)

    lines, progress = [], []
    code = board.flash("COM5", cfg, lines.append, progress.append, popen=popen)
    assert code == 0
    assert seen["argv"] == runner.command("--module", "distrib.runners.flash", "COM5", str(cfg.firmware_dir))
    assert lines[-1] == "[flash] ok" and progress == [0.5]
