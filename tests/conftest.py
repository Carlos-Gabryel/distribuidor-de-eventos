import os
import tempfile
from pathlib import Path

# Antes de importar qualquer coisa do distrib: os testes nunca tocam no %LOCALAPPDATA% real.
os.environ.setdefault("DISTRIB_DATA_DIR", tempfile.mkdtemp(prefix="distrib-tests-"))

import pytest  # noqa: E402

from distrib import config as configmod  # noqa: E402
from distrib.pokeldn_path import ensure_importable  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
CFG = configmod.load()
ensure_importable(CFG.pokeldn_dir)


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def gallery() -> Path:
    return FIXTURES / "gallery"


@pytest.fixture
def cfg(tmp_path) -> configmod.Config:
    return configmod.load(data_dir=tmp_path / "data")
