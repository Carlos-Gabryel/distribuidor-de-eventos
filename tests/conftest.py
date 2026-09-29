import dataclasses
from pathlib import Path

import pytest

from distrib import config as configmod
from distrib.pokeldn_path import ensure_importable

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
    return dataclasses.replace(CFG, catalog_dir=tmp_path / "catalog",
                               state_dir=tmp_path / "state", logs_dir=tmp_path / "logs")
