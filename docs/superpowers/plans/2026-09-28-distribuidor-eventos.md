# Distribuidor de Eventos (pokeldn-distrib): plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Uma TUI de terminal que distribui Pokémon de evento antigos (Sword/Shield por anúncio; FireRed/LeafGreen uma sessão por console) através do pokeldn e de uma ESP32, pronta para levar a encontros num notebook Windows.

**Architecture:** Projeto Python separado (`distrib/`) que usa o pokeldn como biblioteca e como processo filho, sem modificá-lo. Um adaptador por jogo (catálogo, comando do host, leitura do log), um supervisor de processo sem interface (`distributor.py`) e as telas Textual, que só conversam com esses dois. Do lado do Windows, um `.bat`/`.ps1` cuida do WSL e do `usbipd`.

**Tech Stack:** Python 3.12 (WSL2 Ubuntu 24.04), Textual 8.2.8, pytest 8, pokeldn `89f761e` (e o venv dele, `~/.venvs/pokeldn`), PowerShell 5.1, usbipd-win.

**Spec:** `docs/superpowers/specs/2026-09-28-distribuidor-eventos-design.md`

## Global Constraints

- **Nunca modificar o repositório do pokeldn** (`/mnt/c/Gabry/Projects/pokeldn` aqui; `~/pokeldn` no notebook). Só importar e executar.
- pokeldn fixado no commit `89f761e`.
- Python e dependências: **o venv do pokeldn** (`~/.venvs/pokeldn/bin/python`, Python 3.12). Nosso `requirements.txt` só acrescenta `textual==8.2.8` e `pytest>=8,<9`.
- Todo comando de teste roda **dentro do WSL**, na raiz do projeto:
  `cd /mnt/c/Gabry/Projects/pokeldn-distrib && ~/.venvs/pokeldn/bin/python -m pytest …`
  (do Windows: `wsl.exe -- bash -lc 'cd /mnt/c/Gabry/Projects/pokeldn-distrib && ~/.venvs/pokeldn/bin/python -m pytest …'`).
- Os hosts rodam **como root** (`wsl -u root`), com `POKELDN_RADIO=esp32:<porta>`; a porta vem de `/dev/ttyACM*` ou `/dev/ttyUSB*` (o `esp32:auto` do pokeldn não vê `ttyACM`).
- Como root, `~` seria `/root`: caminhos com `~` usam `DISTRIB_USER_HOME` quando definido (o launcher define).
- **Textos da interface em português**; textos gravados no console FRLG em inglês maiúsculo (charset do jogo).
- `prod.keys` nunca entra no repositório nem nos logs.
- Commits terminam com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Fonte do catálogo: `https://codeload.github.com/projectpokemon/EventsGallery/tar.gz/refs/heads/master` (repo de ~56 MB). SwSh: `Released/Gen 8/SwSh/Wondercards/**/*.wc8`. FRLG: `Released/Gen 3/**/*.pk3`.
- Flag ID dos presentes FRLG montados por nós: **1010**. Tempo limite de sessão FRLG: **120 s** (configurável). Falhas seguidas antes de desistir: **3**.

## Review Focus

1. **Placa desplugada ou que some no meio da distribuição** → a tela mostra "placa desconectada" e volta sozinha quando a porta reaparece, sem gastar as 3 tentativas. Teste: Task 8, `test_no_board_waits_without_counting_failures`.
2. **Dois `.pk3` do mesmo evento com PIDs diferentes, e o rodízio sobrevivendo a um reinício da ferramenta** → cada entrega usa o próximo PID, e o índice é salvo em disco. Teste: Task 5, `test_rotation_persists_across_instances`.
3. **Busca com acentos, maiúsculas ou "é" vs "e"** ("pokemon" acha "Pokémon", "zarude" acha "ZARUDE") → a busca ignora caixa e acentos. Teste: Task 3, `test_search_ignores_case_and_accents`.
4. **Trocar de evento enquanto o anterior ainda está no ar** → o host antigo é parado (e esperado) antes de o novo subir, sem dois processos segurando a placa. Teste: Task 8, `test_switch_stops_previous_process_first`.
5. **Catálogo ausente, ou índice de uma versão antiga do formato** → a checagem mostra "catálogo vazio, rode atualizar-catalogo" em vez de quebrar. Teste: Task 3, `test_load_index_missing_or_bad_returns_empty`.

---

## Estrutura de arquivos

```
pokeldn-distrib/
  requirements.txt              Task 1
  config.toml                   Task 1   padrões versionados
  config.local.toml             Task 1   (ignorado) caminhos desta máquina
  distrib/__init__.py           Task 1   vazio
  distrib/config.py             Task 1   Config + load()
  distrib/pokeldn_path.py       Task 1   põe o pokeldn no sys.path
  distrib/frlg_gift.py          Task 2   .pk3 -> WonderGift com givepokemon
  distrib/runners/__init__.py   Task 2
  distrib/runners/frlg_session.py Task 2 host de UMA sessão FRLG
  distrib/catalog.py            Task 3   Event, Catalog, índice JSON, Favorites
  distrib/games/__init__.py     Task 4   ADAPTERS
  distrib/games/base.py         Task 4   Job, Update, contrato
  distrib/games/swsh.py         Task 4   catálogo + job + parser SwSh
  distrib/games/frlg.py         Task 5   catálogo + rodízio + job + parser FRLG
  distrib/download.py           Task 6   baixa e extrai o Events Gallery
  distrib/radio.py              Task 7   acha a porta + HELLO
  distrib/distributor.py        Task 8   supervisor do processo do host
  distrib/app.py                Task 9-10 telas Textual
  distrib/__main__.py           Task 11  CLI: tui | atualizar-catalogo | checar
  windows/iniciar.ps1           Task 12  WSL + usbipd + TUI como root
  "Iniciar Distribuicao.bat"    Task 12  atalho
  windows/instalar.ps1          Task 13  instalação no notebook
  docs/instalacao.md            Task 13
  docs/testes-reais.md          Task 14  roteiro dos testes com consoles
  README.md                     Task 14
  tests/...                     cada task
```

---

### Task 1: Esqueleto, configuração e fixtures

**Files:**
- Create: `requirements.txt`, `config.toml`, `config.local.toml`, `distrib/__init__.py`, `distrib/config.py`, `distrib/pokeldn_path.py`, `tests/__init__.py`, `tests/conftest.py`, `tests/fixtures/baixar.py`, `tests/test_config.py`
- Create (baixados): arquivos em `tests/fixtures/gallery/Released/...`

**Interfaces:**
- Produces: `distrib.config.Config` (campos `project_dir, pokeldn_dir, python, keys, catalog_dir, state_dir, logs_dir: Path`, `frlg_idle_timeout: int`), `distrib.config.load(project_dir: Path = PROJECT_DIR) -> Config`, `distrib.pokeldn_path.ensure_importable(pokeldn_dir: Path) -> None`; fixtures pytest `fixtures -> Path` (pasta `tests/fixtures`), `gallery -> Path` (`tests/fixtures/gallery`), `cfg -> Config` (com `catalog_dir`/`state_dir`/`logs_dir` em `tmp_path`).

- [ ] **Step 1: Arquivos base**

`requirements.txt`:
```
textual==8.2.8
pytest>=8,<9
```

`config.toml`:
```toml
# Padrões. Por máquina, sobrescreva em config.local.toml (ignorado pelo git).
# "~" é a home do usuário do WSL (DISTRIB_USER_HOME quando roda como root).
pokeldn_dir = "~/pokeldn"
python = "~/.venvs/pokeldn/bin/python"
keys = "~/.switch/prod.keys"
frlg_idle_timeout = 120
```

`config.local.toml` (só nesta máquina; está no `.gitignore`):
```toml
pokeldn_dir = "/mnt/c/Gabry/Projects/pokeldn"
```

`distrib/__init__.py` e `tests/__init__.py`: vazios.

`distrib/pokeldn_path.py`:
```python
"""Deixa o pacote do pokeldn e o LDN que ele traz em vendor/ importáveis."""
import sys
from pathlib import Path


def ensure_importable(pokeldn_dir: Path) -> None:
    for path in (pokeldn_dir / "vendor" / "LDN", pokeldn_dir):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
```

- [ ] **Step 2: Instalar as dependências no venv**

Run: `~/.venvs/pokeldn/bin/python -m pip install -r requirements.txt`
Expected: `Successfully installed … textual-8.2.8 … pytest-8.…`

- [ ] **Step 3: Script das fixtures e download**

`tests/fixtures/baixar.py`:
```python
"""Baixa do Events Gallery os poucos arquivos reais usados nos testes (rode uma vez)."""
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/projectpokemon/EventsGallery/master/"
FILES = [
    "Released/Gen 8/SwSh/Wondercards/0507 SWSH - Jungle Zarude (Western Release).wc8",
    "Released/Gen 8/SwSh/Wondercards/0106 SWSH - Item Poke Ball x100.wc8",
    "Released/Gen 3/ENG/10th Anniversary Celebration/Top 10 Distribution/RSEFL - 10ANNIV Lugia (ENG).pk3",
    "Released/Gen 3/ENG/WSHMKR Jirachi/RSEFL - WISHMKR Jirachi (1910) (ENG).pk3",
    "Released/Gen 3/ENG/WSHMKR Jirachi/RSEFL - WISHMKR Jirachi (4CB7) (ENG).pk3",
    "Released/Gen 3/ENG/WISH Eggs/FL - Wish Drowzee Egg (199B613A).pk3",
]

if __name__ == "__main__":
    root = Path(__file__).parent / "gallery"
    for rel in FILES:
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = BASE + urllib.parse.quote(rel)
        dest.write_bytes(urllib.request.urlopen(url, timeout=60).read())
        print(dest.stat().st_size, rel)
```

Run: `~/.venvs/pokeldn/bin/python tests/fixtures/baixar.py`
Expected: seis linhas; `720` para os dois `.wc8` e `80` para os quatro `.pk3`.

- [ ] **Step 4: Escrever o teste da configuração (falha)**

`tests/conftest.py`:
```python
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
```

`tests/test_config.py`:
```python
from pathlib import Path

from distrib import config as configmod


def _project(tmp_path, local=None):
    (tmp_path / "config.toml").write_text(
        'pokeldn_dir = "~/pokeldn"\npython = "~/.venvs/pokeldn/bin/python"\n'
        'keys = "~/.switch/prod.keys"\n', encoding="utf-8")
    if local:
        (tmp_path / "config.local.toml").write_text(local, encoding="utf-8")
    return tmp_path


def test_tilde_uses_distrib_user_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DISTRIB_USER_HOME", "/home/alguem")
    cfg = configmod.load(_project(tmp_path))
    assert cfg.pokeldn_dir == Path("/home/alguem/pokeldn")
    assert cfg.keys == Path("/home/alguem/.switch/prod.keys")
    assert cfg.catalog_dir == tmp_path / "catalog"
    assert cfg.frlg_idle_timeout == 120


def test_local_file_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("DISTRIB_USER_HOME", "/home/alguem")
    cfg = configmod.load(_project(tmp_path, 'pokeldn_dir = "/mnt/c/x/pokeldn"\n'))
    assert cfg.pokeldn_dir == Path("/mnt/c/x/pokeldn")
    assert cfg.python == Path("/home/alguem/.venvs/pokeldn/bin/python")


def test_real_config_points_at_a_pokeldn_checkout():
    cfg = configmod.load()
    assert (cfg.pokeldn_dir / "bin" / "swsh_gift_host.py").exists()
```

- [ ] **Step 5: Rodar e ver falhar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_config.py -v`
Expected: erro de coleta, `ModuleNotFoundError: No module named 'distrib.config'`

- [ ] **Step 6: Implementar `distrib/config.py`**

```python
"""Configuração: config.toml (versionado) + config.local.toml (por máquina, ignorado pelo git)."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    project_dir: Path
    pokeldn_dir: Path
    python: Path
    keys: Path
    catalog_dir: Path
    state_dir: Path
    logs_dir: Path
    frlg_idle_timeout: int


def _user_home() -> Path:
    # Rodando como root (wsl -u root), Path.home() seria /root; o launcher passa a home certa.
    return Path(os.environ.get("DISTRIB_USER_HOME") or Path.home())


def _path(value: str, base: Path) -> Path:
    if value.startswith("~"):
        return _user_home() / value[1:].lstrip("/")
    path = Path(value)
    return path if path.is_absolute() else base / path


def load(project_dir: Path = PROJECT_DIR) -> Config:
    data: dict = {}
    for name in ("config.toml", "config.local.toml"):
        file = project_dir / name
        if file.exists():
            data.update(tomllib.loads(file.read_text(encoding="utf-8")))
    return Config(
        project_dir=project_dir,
        pokeldn_dir=_path(data["pokeldn_dir"], project_dir),
        python=_path(data["python"], project_dir),
        keys=_path(data["keys"], project_dir),
        catalog_dir=_path(data.get("catalog_dir", "catalog"), project_dir),
        state_dir=_path(data.get("state_dir", "state"), project_dir),
        logs_dir=_path(data.get("logs_dir", "logs"), project_dir),
        frlg_idle_timeout=int(data.get("frlg_idle_timeout", 120)),
    )
```

- [ ] **Step 7: Rodar e ver passar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_config.py -v`
Expected: 3 passed

- [ ] **Step 8: Commit**

```bash
git add requirements.txt config.toml distrib tests
git commit -m "feat: esqueleto, configuração e fixtures reais do Events Gallery

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Presente FRLG a partir de `.pk3` + runner de uma sessão + PROVA DE CONCEITO no FireRed

**Esta task bloqueia as Tasks 5 e seguintes na parte FRLG.** Se o Step 8 falhar, pare e registre o resultado. A v1 do FRLG fica só com os extras (a Task 5 perde o catálogo `.pk3`).

**Files:**
- Create: `distrib/frlg_gift.py`, `distrib/runners/__init__.py` (vazio), `distrib/runners/frlg_session.py`, `tests/test_frlg_gift.py`

**Interfaces:**
- Consumes: `ensure_importable` (Task 1).
- Produces: `distrib.frlg_gift.FLAG_ID = 1010`, `GiftError(Exception)`, `load_mon(path: Path) -> Mon` (valida checksum, espécie e ovo), `is_egg(mon) -> bool`, `build_gift(path: Path) -> WonderGift`, `register(path: Path) -> str` (slug `distrib-<pid:08x>`), `describe(path: Path) -> str`. Runner: `python -m distrib.runners.frlg_session --pokeldn DIR (--pk3 ARQ | --extra SLUG) [args do frlg_mg_host…]`, com os códigos de saída do `frlg_mg_host` (0 entregue, 1 não entregue, 124 sem console, 130 interrompido).

- [ ] **Step 1: Escrever os testes (falham)**

`tests/test_frlg_gift.py`:
```python
import pytest

from distrib import frlg_gift
from distrib.runners import frlg_session

G3 = "Released/Gen 3/ENG"
LUGIA = f"{G3}/10th Anniversary Celebration/Top 10 Distribution/RSEFL - 10ANNIV Lugia (ENG).pk3"
EGG = f"{G3}/WISH Eggs/FL - Wish Drowzee Egg (199B613A).pk3"


def test_build_gift_carries_the_whole_mon(gallery):
    from pokeldn.frlg.rom import mystery_event
    gift = frlg_gift.build_gift(gallery / LUGIA)
    assert gift.slug == "distrib-828027a9"
    assert gift.card.icon_species == 249
    assert gift.card.default_flag_id == frlg_gift.FLAG_ID
    assert mystery_event.describe(gift.mevent).startswith("givepokemon")


def test_register_validates_and_is_idempotent(gallery):
    from pokeldn.frlg.gift.gift_registry import GIFT_REGISTRY
    slug = frlg_gift.register(gallery / LUGIA)
    assert slug in GIFT_REGISTRY.live_choices
    assert frlg_gift.register(gallery / LUGIA) == slug


def test_egg_is_refused(gallery):
    with pytest.raises(frlg_gift.GiftError, match="ovo"):
        frlg_gift.load_mon(gallery / EGG)


def test_garbage_is_refused(tmp_path):
    bad = tmp_path / "lixo.pk3"
    bad.write_bytes(bytes(range(80)))
    with pytest.raises(frlg_gift.GiftError):
        frlg_gift.load_mon(bad)


def test_describe(gallery):
    assert frlg_gift.describe(gallery / LUGIA) == "LUGIA Nv70 OT 10ANNIV PID 828027a9"


def test_runner_registers_before_the_host_parser(gallery, capsys):
    from distrib import config
    with pytest.raises(SystemExit) as exc:
        frlg_session.main(["--pokeldn", str(config.load().pokeldn_dir),
                           "--pk3", str(gallery / LUGIA), "--help"])
    assert exc.value.code == 0
    assert "distrib-828027a9" in capsys.readouterr().out
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_frlg_gift.py -v`
Expected: erro de coleta, `ImportError: cannot import name 'frlg_gift' from 'distrib'`

- [ ] **Step 3: Implementar `distrib/frlg_gift.py`**

Pré-condição: `ensure_importable(pokeldn_dir)` já foi chamado (o conftest e o runner fazem isso).

```python
"""O presente do FRLG que entrega um .pk3 inteiro, byte a byte, pelo `givepokemon` do Mystery Event.

O console copia a struct Pokemon (100 bytes, criptografada) para a equipe e marca a Pokédex;
o Pokémon chega com o OT, o ID e o PID do arquivo. Equipe cheia -> status 3, nada é escrito.
"""
from __future__ import annotations

from pathlib import Path

from pokeldn.frlg.gift.gift_composer import (
    DeliveryPlan, DeliveryStage, GiftSpec, Message, WonderCardSpec, WonderGift)
from pokeldn.frlg.gift.gift_registry import GIFT_REGISTRY
from pokeldn.frlg.rom import mystery_event
from pokeldn.frlg.save import basestats, mevent_pokemon
from pokeldn.frlg.save.mon import Mon

FLAG_ID = 1010
_IS_EGG = 0x04      # BoxPokemon byte 0x13: isBadEgg:1, hasSpecies:1, isEgg:1 [decomp:include/pokemon.h]


class GiftError(Exception):
    """Um .pk3 que não pode ser entregue."""


def is_egg(mon: Mon) -> bool:
    return bool(mon.raw[19] & _IS_EGG)


def load_mon(path: Path) -> Mon:
    try:
        mon = Mon.from_file(path)
    except ValueError as exc:
        raise GiftError(f"{path.name}: {exc}") from exc
    decoded = mon.decode()
    if not decoded or not decoded["checksum_ok"]:
        raise GiftError(f"{path.name}: checksum inválido")
    if decoded["species"] not in basestats.BASE_STATS:
        raise GiftError(f"{path.name}: espécie {decoded['species']} desconhecida")
    if is_egg(mon):
        raise GiftError(f"{path.name}: é um ovo (fora da v1)")
    return mon


def describe(path: Path) -> str:
    mon = load_mon(path)
    d = mon.decode()
    return f"{d['nickname']} Nv{d['level']} OT {d['otName']} PID {d['pid']:08x}"


def build_gift(path: Path) -> WonderGift:
    mon = load_mon(path)
    script = mystery_event.MysteryEventScript()
    script.givepokemon(script.blob(mevent_pokemon.build_givepokemon_payload(mon))).end()
    return WonderGift(
        slug=f"distrib-{mon.pid:08x}",
        card=WonderCardSpec(
            icon_species=mon.species,
            title="MYSTERY EVENT",
            subtitle="A GIFT FROM THE PAST",
            body=("A special POKEMON from a past",
                  "event was sent straight to your",
                  "party."),
            footer1="pokeldn-distrib",
            default_flag_id=FLAG_ID),
        intro_message="Thank you for using the MYSTERY\nGIFT System.",
        event=GiftSpec(repeatable=True),
        delivery=DeliveryPlan(delivery=(
            DeliveryStage(Message("The POKEMON was sent straight to\nyour party, {PLAYER}.")),
        )),
        completed_message="The POKEMON went straight to your\nparty.",
        mevent=script.assemble(),
    )


def register(path: Path) -> str:
    gift = build_gift(path)
    if gift.slug not in GIFT_REGISTRY.live_choices:
        GIFT_REGISTRY.register_definition(gift)     # valida e compila; ValueError se algo não cabe
    return gift.slug
```

- [ ] **Step 4: Implementar `distrib/runners/frlg_session.py`**

```python
"""Host de UMA sessão do Mystery Gift do FireRed/LeafGreen (rodar como root).

    python -m distrib.runners.frlg_session --pokeldn DIR --pk3 ARQ [args do frlg_mg_host]
    python -m distrib.runners.frlg_session --pokeldn DIR --extra altering-cave [args…]

Registra o nosso presente no GIFT_REGISTRY antes de o parser do bin/frlg_mg_host.py ser montado
(as opções de --gift saem do registro) e chama o main() dele com --end-on-success.
Sai com o código do host: 0 entregue, 1 não entregue, 124 sem console, 130 interrompido.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from distrib.pokeldn_path import ensure_importable


def load_host(pokeldn_dir: Path):
    spec = importlib.util.spec_from_file_location(
        "frlg_mg_host", pokeldn_dir / "bin" / "frlg_mg_host.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--pokeldn", required=True, type=Path)
    what = parser.add_mutually_exclusive_group(required=True)
    what.add_argument("--pk3", type=Path)
    what.add_argument("--extra")
    args, host_args = parser.parse_known_args(argv)
    if host_args[:1] == ["--"]:
        host_args = host_args[1:]
    ensure_importable(args.pokeldn)
    if args.pk3 is not None:
        from distrib import frlg_gift
        slug = frlg_gift.register(args.pk3)
        print(f"[distrib] presente {slug}: {frlg_gift.describe(args.pk3)}", flush=True)
    else:
        slug = args.extra
        print(f"[distrib] extra {slug}", flush=True)
    host = load_host(args.pokeldn)
    return host.main(["--live", "--gift", slug, "--end-on-success", *host_args])


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Rodar os testes e ver passar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_frlg_gift.py -v`
Expected: 6 passed. Se `test_describe` falhar só na formatação do nível ou do OT, ajuste a string esperada ao que `decode()` devolve (verificado em 2026-09-28: `LUGIA`, nível 70, OT `10ANNIV`, PID `828027a9`).

- [ ] **Step 6: Commit**

```bash
git add distrib/frlg_gift.py distrib/runners tests/test_frlg_gift.py
git commit -m "feat(frlg): presente givepokemon a partir de .pk3 e runner de uma sessão

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 7: Prova de conceito no FireRed (com o dono)**

A placa precisa estar no WSL (`usbipd attach --wsl --busid <X>`; hoje `/dev/ttyACM0`). No FireRed: **MYSTERY GIFT** no menu inicial → **WONDER CARDS** → **FRIEND** e deixar buscando. (Se não houver MYSTERY GIFT no menu inicial, ele é destravado respondendo o questionário de uma POKé MART com `LINK TOGETHER WITH ALL`.) Garanta pelo menos **um espaço livre na equipe**.

Run (do Windows):
```bash
wsl.exe -u root -- bash -lc 'cd /mnt/c/Gabry/Projects/pokeldn-distrib && POKELDN_RADIO=esp32:/dev/ttyACM0 /home/gabryel/.venvs/pokeldn/bin/python -u -m distrib.runners.frlg_session --pokeldn /mnt/c/Gabry/Projects/pokeldn --pk3 "tests/fixtures/gallery/Released/Gen 3/ENG/10th Anniversary Celebration/Top 10 Distribution/RSEFL - 10ANNIV Lugia (ENG).pk3" --keys /home/gabryel/.switch/prod.keys --phy auto --idle-timeout 300 > /root/frlg_poc.log 2>&1; echo EXIT=$? >> /root/frlg_poc.log'
```
O host aparece no FireRed; o dono escolhe e confirma.

- [ ] **Step 8: Verificar o resultado**

Run: `wsl.exe -u root -- bash -lc 'grep -v "^\[status\]" /root/frlg_poc.log | tail -40'`
Expected:
- uma linha `Mystery Event script status: 2 (success)` e `EXIT=0`;
- no FireRed, o Lugia na equipe: Nv70, OT **10ANNIV**, e no resumo o "fateful encounter" / local de encontro de evento.

**Também anote no Step 9** as linhas exatas que o host imprimiu: (a) quando começou a anunciar (esperado: `Advertising ACTIVITY_WONDER_CARD…`), (b) quando o console entrou na sessão, (c) o resultado. A Task 5 usa essas linhas no parser.

Se falhar: guarde o log em `docs/poc-frlg-falhou.log` (sem o caminho do `prod.keys`), registre a causa e siga o plano **sem** o catálogo `.pk3` (Task 5: só os extras).

- [ ] **Step 9: Registrar a prova de conceito**

Crie `docs/poc-frlg.md` com a data, o comando, as três linhas do log (a/b/c do Step 8), o resultado no console e fotos/descrição do resumo do Pokémon. Commit:
```bash
git add docs/poc-frlg.md
git commit -m "docs: prova de conceito FRLG (.pk3 do Events Gallery no FireRed)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Modelo do catálogo, índice JSON e favoritos

**Files:**
- Create: `distrib/catalog.py`, `tests/test_catalog.py`

**Interfaces:**
- Produces:
  - `Event` (frozen dataclass): `game: str`, `key: str`, `name: str`, `kind: str` (`"pokemon"`, `"item"` ou `"extra"`), `details: tuple[tuple[str, str], ...]` (rótulo, valor, na ordem de exibição), `files: tuple[str, ...]` (caminhos relativos ao `catalog_dir/<game>/`; vazio nos extras), `sort_key: str`. Propriedade `search_text: str`.
  - `Catalog`: `game: str`, `events: list[Event]`, `invalid: int = 0`; `search(text: str = "", include_items: bool = False) -> list[Event]`; `get(key: str) -> Event`.
  - `normalize(text: str) -> str` (minúsculas, sem acentos).
  - `INDEX_VERSION = 1`, `save_index(catalog: Catalog, path: Path) -> None`, `load_index(game: str, path: Path) -> Catalog` (índice ausente/antigo/corrompido → catálogo vazio).
  - `Favorites(path: Path)`: `contains(event) -> bool`, `toggle(event) -> bool` (novo estado), salva a cada mudança.

- [ ] **Step 1: Escrever os testes (falham)**

`tests/test_catalog.py`:
```python
import json

from distrib.catalog import (INDEX_VERSION, Catalog, Event, Favorites, load_index, normalize,
                             save_index)


def ev(key, name, kind="pokemon", sort_key=None):
    return Event(game="swsh", key=key, name=name, kind=kind,
                 details=(("Espécie", "#893"),), files=(f"{key}.wc8",),
                 sort_key=sort_key or key)


def sample():
    return Catalog("swsh", [ev("b", "Jungle Zarude"), ev("a", "Pokémon Quest Tee", "item"),
                            ev("c", "Shiny Celebi")])


def test_normalize():
    assert normalize("Pokémon ÉÇÃ") == "pokemon eca"


def test_search_ignores_case_and_accents():
    cat = sample()
    assert [e.key for e in cat.search("ZARUDE")] == ["b"]
    assert [e.key for e in cat.search("pokemon", include_items=True)] == ["a"]


def test_search_hides_items_by_default_and_sorts():
    cat = sample()
    assert [e.key for e in cat.search("")] == ["b", "c"]
    assert [e.key for e in cat.search("", include_items=True)] == ["a", "b", "c"]


def test_get():
    assert sample().get("c").name == "Shiny Celebi"


def test_index_roundtrip(tmp_path):
    cat = sample()
    cat.invalid = 2
    path = tmp_path / "swsh" / "index.json"
    save_index(cat, path)
    back = load_index("swsh", path)
    assert back.events == cat.events
    assert back.invalid == 2


def test_load_index_missing_or_bad_returns_empty(tmp_path):
    assert load_index("swsh", tmp_path / "nao-existe.json").events == []
    bad = tmp_path / "bad.json"
    bad.write_text("{isto nao e json", encoding="utf-8")
    assert load_index("swsh", bad).events == []
    old = tmp_path / "old.json"
    old.write_text(json.dumps({"version": INDEX_VERSION + 99, "events": []}), encoding="utf-8")
    assert load_index("swsh", old).events == []


def test_favorites_toggle_and_persist(tmp_path):
    path = tmp_path / "state" / "favoritos.json"
    fav = Favorites(path)
    e = ev("b", "Jungle Zarude")
    assert fav.toggle(e) is True
    assert Favorites(path).contains(e)
    assert fav.toggle(e) is False
    assert not Favorites(path).contains(e)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_catalog.py -v`
Expected: erro de coleta, `ModuleNotFoundError: No module named 'distrib.catalog'`

- [ ] **Step 3: Implementar `distrib/catalog.py`**

```python
"""O catálogo de um jogo: eventos, busca, índice em JSON e a vitrine do dia (favoritos)."""
from __future__ import annotations

import json
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

INDEX_VERSION = 1


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


@dataclass(frozen=True)
class Event:
    game: str
    key: str
    name: str
    kind: str                                   # "pokemon" | "item" | "extra"
    details: tuple[tuple[str, str], ...]
    files: tuple[str, ...]
    sort_key: str

    @property
    def search_text(self) -> str:
        return normalize(" ".join([self.name, *(v for _, v in self.details)]))


@dataclass
class Catalog:
    game: str
    events: list[Event] = field(default_factory=list)
    invalid: int = 0

    def search(self, text: str = "", include_items: bool = False) -> list[Event]:
        words = normalize(text).split()
        found = [e for e in self.events
                 if (include_items or e.kind != "item")
                 and all(w in e.search_text for w in words)]
        return sorted(found, key=lambda e: e.sort_key)

    def get(self, key: str) -> Event:
        for event in self.events:
            if event.key == key:
                return event
        raise KeyError(key)


def save_index(catalog: Catalog, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"version": INDEX_VERSION, "game": catalog.game, "invalid": catalog.invalid,
            "events": [asdict(e) for e in catalog.events]}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def load_index(game: str, path: Path) -> Catalog:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version") != INDEX_VERSION:
            return Catalog(game)
        events = [Event(game=e["game"], key=e["key"], name=e["name"], kind=e["kind"],
                        details=tuple(tuple(d) for d in e["details"]),
                        files=tuple(e["files"]), sort_key=e["sort_key"])
                  for e in data["events"]]
        return Catalog(game, events, int(data.get("invalid", 0)))
    except (OSError, ValueError, KeyError, TypeError):
        return Catalog(game)


class Favorites:
    def __init__(self, path: Path):
        self.path = path
        try:
            self._keys = set(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            self._keys = set()

    @staticmethod
    def _id(event: Event) -> str:
        return f"{event.game}:{event.key}"

    def contains(self, event: Event) -> bool:
        return self._id(event) in self._keys

    def toggle(self, event: Event) -> bool:
        ident = self._id(event)
        if ident in self._keys:
            self._keys.discard(ident)
        else:
            self._keys.add(ident)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(sorted(self._keys), ensure_ascii=False), encoding="utf-8")
        return ident in self._keys
```

- [ ] **Step 4: Rodar e ver passar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_catalog.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add distrib/catalog.py tests/test_catalog.py
git commit -m "feat: modelo do catálogo, busca sem acentos, índice JSON e favoritos

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Contrato dos jogos e adaptador Sword/Shield

**Files:**
- Create: `distrib/games/__init__.py`, `distrib/games/base.py`, `distrib/games/swsh.py`, `tests/test_swsh.py`

**Interfaces:**
- Consumes: `Config` (Task 1), `Event`, `Catalog`, `save_index` (Task 3).
- Produces:
  - `distrib.games.base.Job` (frozen): `argv: tuple[str, ...]`, `env: dict[str, str]`, `cwd: str`, `label: str` (o que é mostrado como "entregando").
  - `distrib.games.base.Update` (frozen): `state: str | None = None` (um de `"on_air"`, `"console"`, `"delivered"`, `"party_full"`, `"not_delivered"`, `"error"`), `channel: int | None = None`, `detail: str | None = None`.
  - `distrib.games.base.Adapter` (Protocol): `game: str`, `title: str`, `mode: str` (`"broadcast"` | `"session"`), `instructions: str`; `build_catalog(raw_dir: Path, cfg: Config) -> Catalog` (lê `raw_dir`, grava arquivos e `index.json` em `cfg.catalog_dir/<game>/`); `build_job(event: Event, cfg: Config, port: str) -> Job`; `parse_line(line: str) -> Update | None`.
  - `distrib.games.swsh.SwshAdapter()`; `SWSH_RAW = "Released/Gen 8/SwSh/Wondercards"`.
  - `distrib.games.ADAPTERS: dict[str, Adapter]` (nesta task só `"swsh"`; a Task 5 acrescenta `"frlg"`).

- [ ] **Step 1: Escrever os testes (falham)**

`tests/test_swsh.py`:
```python
from distrib.games import swsh
from distrib.games.base import Update

A = swsh.SwshAdapter()


def build(gallery, cfg):
    return A.build_catalog(gallery / swsh.SWSH_RAW, cfg)


def test_catalog_one_event_per_file(gallery, cfg):
    cat = build(gallery, cfg)
    assert {e.name for e in cat.events} == {"Jungle Zarude (Western Release)",
                                            "Item Poke Ball x100"}
    zarude = next(e for e in cat.events if "Zarude" in e.name)
    assert zarude.kind == "pokemon"
    details = dict(zarude.details)
    assert details["Espécie"] == "#893"
    assert details["Nível"] == "60"
    assert details["Shiny"] == "nunca"
    assert details["Jogos"] == "Sword e Shield"
    assert details["Cartão"] == "#0507"
    poke_ball = next(e for e in cat.events if "Poke Ball" in e.name)
    assert poke_ball.kind == "item"


def test_catalog_copies_files_and_writes_index(gallery, cfg):
    cat = build(gallery, cfg)
    base = cfg.catalog_dir / "swsh"
    assert (base / "index.json").exists()
    for event in cat.events:
        assert (base / event.files[0]).stat().st_size == 720


def test_catalog_reseals_and_counts_invalid(gallery, cfg, tmp_path):
    from pokeldn.swsh import wc8
    raw = tmp_path / "raw"
    raw.mkdir()
    good = (gallery / swsh.SWSH_RAW / "0106 SWSH - Item Poke Ball x100.wc8").read_bytes()
    broken = bytearray(good)
    broken[wc8.CHECKSUM_AT] ^= 0xFF
    (raw / "0106 SWSH - Quebrado.wc8").write_bytes(bytes(broken))
    (raw / "0001 SWSH - Curto.wc8").write_bytes(good[:100])
    cat = A.build_catalog(raw, cfg)
    assert [e.name for e in cat.events] == ["Quebrado"]
    assert wc8.sealed((cfg.catalog_dir / "swsh" / cat.events[0].files[0]).read_bytes())
    assert cat.invalid == 1


def test_subfolder_goes_into_the_name(gallery, cfg, tmp_path):
    raw = tmp_path / "raw"
    (raw / "Ranked Battles").mkdir(parents=True)
    src = gallery / swsh.SWSH_RAW / "0106 SWSH - Item Poke Ball x100.wc8"
    (raw / "Ranked Battles" / "0002 SWSH - Doubles S1 Battle Points x50.wc8").write_bytes(
        src.read_bytes())
    cat = A.build_catalog(raw, cfg)
    assert cat.events[0].name == "Ranked Battles: Doubles S1 Battle Points x50"


def test_build_job(gallery, cfg):
    event = build(gallery, cfg).search("zarude")[0]
    job = A.build_job(event, cfg, "/dev/ttyACM0")
    assert job.env["POKELDN_RADIO"] == "esp32:/dev/ttyACM0"
    assert job.argv[0] == str(cfg.python)
    assert job.argv[1:3] == ("-u", str(cfg.pokeldn_dir / "bin" / "swsh_gift_host.py"))
    assert "--no-validate" in job.argv
    record = job.argv[job.argv.index("--record") + 1]
    assert record == str(cfg.catalog_dir / "swsh" / event.files[0])
    assert job.argv[job.argv.index("--keys") + 1] == str(cfg.keys)
    assert job.cwd == str(cfg.pokeldn_dir)


def test_parse_line():
    assert A.parse_line("[host] AP up: ssid=59 ch=11 us=169.254.99.1/x") == Update(channel=11)
    assert A.parse_line("advertising comm id 0x0100abf008968000, scene 0, protocol 1") \
        == Update(state="on_air")
    assert A.parse_line("RuntimeError: LDN host bring-up failed after 3 attempt(s):") \
        == Update(state="error", detail="RuntimeError: LDN host bring-up failed after 3 attempt(s):")
    assert A.parse_line("[status] mode=0 rx_mgmt=1") is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_swsh.py -v`
Expected: erro de coleta, `ModuleNotFoundError: No module named 'distrib.games'`

- [ ] **Step 3: Implementar `distrib/games/base.py`**

```python
"""O contrato que cada jogo cumpre; as telas e o distributor só conhecem isto."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from distrib.catalog import Catalog, Event
from distrib.config import Config

STATES = ("on_air", "console", "delivered", "party_full", "not_delivered", "error")


@dataclass(frozen=True)
class Job:
    argv: tuple[str, ...]
    env: dict[str, str] = field(default_factory=dict)
    cwd: str = "."
    label: str = ""


@dataclass(frozen=True)
class Update:
    state: str | None = None
    channel: int | None = None
    detail: str | None = None


class Adapter(Protocol):
    game: str
    title: str
    mode: str               # "broadcast" (SwSh) | "session" (FRLG)
    instructions: str

    def build_catalog(self, raw_dir: Path, cfg: Config) -> Catalog: ...

    def build_job(self, event: Event, cfg: Config, port: str) -> Job: ...

    def parse_line(self, line: str) -> Update | None: ...
```

- [ ] **Step 4: Implementar `distrib/games/swsh.py`**

```python
"""Sword/Shield: Wonder Cards .wc8 anunciados pelo bin/swsh_gift_host.py (vários consoles de uma vez)."""
from __future__ import annotations

import re
from pathlib import Path

from distrib.catalog import Catalog, Event, save_index
from distrib.config import Config
from distrib.games.base import Job, Update

SWSH_RAW = "Released/Gen 8/SwSh/Wondercards"
SHINY = {0: "nunca", 1: "possível", 2: "sempre (estrela)", 3: "sempre (quadrado)",
         4: "fixo pelo PID"}
GAMES = {1: "Sword", 2: "Shield", 3: "Sword e Shield"}
_PREFIX = re.compile(r"^\d{4} (?:SWSH|SW|SH) - ")
_CHANNEL = re.compile(r"\[host\] AP up: .* ch=(\d+)")


def clean_name(path: Path, raw_dir: Path) -> str:
    name = _PREFIX.sub("", path.stem)
    parent = path.parent.relative_to(raw_dir)
    return f"{parent.as_posix()}: {name}" if str(parent) != "." else name


class SwshAdapter:
    game = "swsh"
    title = "Sword/Shield"
    mode = "broadcast"
    instructions = ("Nos consoles: Presente Misterioso → Receber presente → "
                    "Por comunicação local")

    def build_catalog(self, raw_dir: Path, cfg: Config) -> Catalog:
        from pokeldn.swsh import wc8
        out = cfg.catalog_dir / self.game
        out.mkdir(parents=True, exist_ok=True)
        catalog = Catalog(self.game)
        for index, path in enumerate(sorted(raw_dir.rglob("*.wc8"))):
            rec = path.read_bytes()
            if len(rec) != wc8.RECORD:
                catalog.invalid += 1
                continue
            if not wc8.sealed(rec):
                rec = bytes(wc8.seal(bytearray(rec)))
            info = wc8.read(rec)
            file_name = f"{index:04d}.wc8"
            (out / file_name).write_bytes(rec)
            catalog.events.append(self._event(info, clean_name(path, raw_dir), file_name))
        save_index(catalog, out / "index.json")
        return catalog

    def _event(self, info: dict, name: str, file_name: str) -> Event:
        pokemon = info["kind"] == 1
        details = [("Cartão", f"#{info['card_id']:04d}"),
                   ("Jogos", GAMES.get(info["region_mask"] & 3, "?"))]
        if pokemon:
            own_ids = info["tid"] == 0 and info["sid"] == 0
            details += [("Espécie", f"#{info['species']}"),
                        ("Nível", str(info["level"]) if info["level"] else "aleatório"),
                        ("Shiny", SHINY.get(info["shiny_type"], str(info["shiny_type"]))),
                        ("Gigantamax", "sim" if info["gigantamax"] else "não"),
                        ("OT", info["ot"] or "do jogador"),
                        ("TID/SID", "do jogador" if own_ids else f"{info['tid']}/{info['sid']}")]
        return Event(game=self.game, key=file_name, name=name,
                     kind="pokemon" if pokemon else "item", details=tuple(details),
                     files=(file_name,), sort_key=f"{info['card_id']:04d} {name}")

    def build_job(self, event: Event, cfg: Config, port: str) -> Job:
        record = cfg.catalog_dir / self.game / event.files[0]
        return Job(
            argv=(str(cfg.python), "-u", str(cfg.pokeldn_dir / "bin" / "swsh_gift_host.py"),
                  "--record", str(record), "--keys", str(cfg.keys),
                  "--seconds", "86400", "--no-validate"),
            env={"POKELDN_RADIO": f"esp32:{port}"},
            cwd=str(cfg.pokeldn_dir), label=event.name)

    def parse_line(self, line: str) -> Update | None:
        if match := _CHANNEL.search(line):
            return Update(channel=int(match.group(1)))
        if line.startswith("advertising comm id"):
            return Update(state="on_air")
        if line.startswith(("RuntimeError", "Traceback", "OSError", "PermissionError")):
            return Update(state="error", detail=line.strip())
        return None
```

`distrib/games/__init__.py`:
```python
from distrib.games.swsh import SwshAdapter

ADAPTERS = {"swsh": SwshAdapter()}
```

- [ ] **Step 5: Rodar e ver passar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_swsh.py -v`
Expected: 6 passed. (`test_catalog_reseals_and_counts_invalid`: o arquivo curto conta como inválido e o de checksum quebrado é re-selado.)

- [ ] **Step 6: Commit**

```bash
git add distrib/games tests/test_swsh.py
git commit -m "feat(swsh): contrato dos jogos e adaptador Sword/Shield

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Adaptador FireRed/LeafGreen (catálogo .pk3, rodízio de PID, extras)

**Files:**
- Create: `distrib/games/frlg.py`, `tests/test_frlg.py`
- Modify: `distrib/games/__init__.py`

**Interfaces:**
- Consumes: `Job`, `Update`, `Adapter` (Task 4); `frlg_gift.load_mon`, `GiftError` (Task 2); `Catalog`, `Event`, `save_index` (Task 3).
- Produces: `distrib.games.frlg.FrlgAdapter(rotation_path: Path | None = None)`; `FRLG_RAW = "Released/Gen 3"`; `EXTRAS: tuple[tuple[str, str, str], ...]` (slug, nome, descrição); `Rotation(path: Path)` com `next_file(event: Event) -> str`; `event_name(path: Path) -> str`; `ADAPTERS["frlg"]`.
- O `build_job` do FRLG escolhe a variante com o `Rotation` (cada chamada avança). Um `Event` com `kind == "extra"` tem `key == "extra:<slug>"`.

- [ ] **Step 1: Escrever os testes (falham)**

`tests/test_frlg.py`:
```python
from distrib.games import frlg
from distrib.games.base import Update


def adapter(cfg):
    return frlg.FrlgAdapter(cfg.state_dir / "rodizio_pid.json")


def test_event_name_strips_prefix_and_pid_tag():
    from pathlib import Path
    assert frlg.event_name(Path("RSEFL - WISHMKR Jirachi (1910) (ENG).pk3")) \
        == "WISHMKR Jirachi (ENG)"
    assert frlg.event_name(Path("FL - Wish Drowzee Egg (199B613A).pk3")) == "Wish Drowzee Egg"
    assert frlg.event_name(Path("RSEFL - 10ANNIV Lugia (ENG).pk3")) == "10ANNIV Lugia (ENG)"


def test_catalog_groups_pid_variants_and_skips_eggs(gallery, cfg):
    cat = adapter(cfg).build_catalog(gallery / frlg.FRLG_RAW, cfg)
    pokemon = {e.name: e for e in cat.events if e.kind == "pokemon"}
    assert set(pokemon) == {"WISHMKR Jirachi (ENG)", "10ANNIV Lugia (ENG)"}
    assert len(pokemon["WISHMKR Jirachi (ENG)"].files) == 2
    details = dict(pokemon["10ANNIV Lugia (ENG)"].details)
    assert details["OT"] == "10ANNIV"
    assert details["Nível"] == "70"
    assert details["Variantes (PID)"] == "1"
    assert details["Pasta"] == "ENG/10th Anniversary Celebration/Top 10 Distribution"
    assert cat.invalid == 1                      # o ovo
    for event in pokemon.values():
        for f in event.files:
            assert (cfg.catalog_dir / "frlg" / f).stat().st_size == 80


def test_catalog_includes_extras(gallery, cfg):
    cat = adapter(cfg).build_catalog(gallery / frlg.FRLG_RAW, cfg)
    extras = [e for e in cat.events if e.kind == "extra"]
    assert {e.key for e in extras} == {f"extra:{slug}" for slug, _, _ in frlg.EXTRAS}
    assert all(e.files == () for e in extras)


def test_rotation_cycles_variants(gallery, cfg):
    a = adapter(cfg)
    cat = a.build_catalog(gallery / frlg.FRLG_RAW, cfg)
    jirachi = cat.search("jirachi")[0]
    firsts = [a.build_job(jirachi, cfg, "/dev/ttyACM0") for _ in range(3)]
    pk3s = [j.argv[j.argv.index("--pk3") + 1] for j in firsts]
    assert pk3s[0] != pk3s[1]
    assert pk3s[0] == pk3s[2]


def test_rotation_persists_across_instances(gallery, cfg):
    a = adapter(cfg)
    jirachi = a.build_catalog(gallery / frlg.FRLG_RAW, cfg).search("jirachi")[0]
    first = a.build_job(jirachi, cfg, "/dev/ttyACM0")
    second = adapter(cfg).build_job(jirachi, cfg, "/dev/ttyACM0")
    assert first.argv[first.argv.index("--pk3") + 1] != second.argv[second.argv.index("--pk3") + 1]


def test_build_job_for_pk3_and_extra(gallery, cfg):
    a = adapter(cfg)
    cat = a.build_catalog(gallery / frlg.FRLG_RAW, cfg)
    job = a.build_job(cat.search("lugia")[0], cfg, "/dev/ttyACM0")
    assert job.argv[:4] == (str(cfg.python), "-u", "-m", "distrib.runners.frlg_session")
    assert job.argv[job.argv.index("--pokeldn") + 1] == str(cfg.pokeldn_dir)
    assert job.argv[job.argv.index("--idle-timeout") + 1] == str(cfg.frlg_idle_timeout)
    assert job.env["POKELDN_RADIO"] == "esp32:/dev/ttyACM0"
    assert job.cwd == str(cfg.project_dir)
    extra = cat.get("extra:altering-cave")
    job = a.build_job(extra, cfg, "/dev/ttyACM0")
    assert job.argv[job.argv.index("--extra") + 1] == "altering-cave"


def test_parse_line():
    a = frlg.FrlgAdapter(None)
    assert a.parse_line("Advertising ACTIVITY_WONDER_CARD. On the Switch choose ...") \
        == Update(state="on_air")
    assert a.parse_line("Mystery Event script status: 2 (success)") == Update(state="delivered")
    assert a.parse_line("Mystery Event script status: 3 (incompatible, or givepokemon found "
                        "a full party)") == Update(state="party_full")
    assert a.parse_line("Wonder Card delivered. On the Switch, talk to the delivery man") \
        == Update(state="delivered")
    assert a.parse_line("Session finished without delivering anything: x") \
        == Update(state="not_delivered", detail="Session finished without delivering anything: x")
    assert a.parse_line("[distrib] presente distrib-828027a9: LUGIA Nv70 OT 10ANNIV PID 828027a9") \
        == Update(detail="LUGIA Nv70 OT 10ANNIV PID 828027a9")
    assert a.parse_line("[status] mode=0") is None
```

Se a prova de conceito (Task 2, Step 8) registrou uma linha própria para "console entrou", acrescente ao `test_parse_line` a asserção `a.parse_line(<essa linha>) == Update(state="console")`, e ao `_CONSOLE` abaixo o texto exato dela.

- [ ] **Step 2: Rodar e ver falhar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_frlg.py -v`
Expected: erro de coleta, `ImportError: cannot import name 'frlg' from 'distrib.games'`

- [ ] **Step 3: Implementar `distrib/games/frlg.py`**

```python
"""FireRed/LeafGreen: um console por sessão, pelo nosso runner (distrib.runners.frlg_session)."""
from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

from distrib.catalog import Catalog, Event, save_index
from distrib.config import Config
from distrib.games.base import Job, Update

FRLG_RAW = "Released/Gen 3"
LANGUAGES = {1: "JPN", 2: "ENG", 3: "FRE", 4: "ITA", 5: "GER", 7: "SPA"}
EXTRAS = (
    ("altering-cave", "Altering Cave (evento oficial)", "Muda os Pokémon da Altering Cave"),
    ("battle-count-card", "Battle Count Card (oficial)", "Cartão que conta batalhas e trocas"),
    ("beast-cutscene-share", "Cena da fera lendária", "Cena repetível da fera lendária"),
    ("celebi", "Celebi Nv50 (montado pelo pokeldn)", "Celebi entregue pelo entregador"),
    ("porygon-tm-gift", "Porygon + TMs", "Porygon, cena da Clefairy, TM29 e TM46"),
    ("solrock-stamp", "Stamp Rally: Solrock", "Metade Solrock do Sun and Moon Rally"),
    ("lunatone-stamp", "Stamp Rally: Lunatone", "Metade Lunatone do Sun and Moon Rally"),
    ("master-ball", "Master Ball", "Uma Master Ball pelo entregador"),
    ("worlds-xp", "Worlds 26 (FANtastic Mystery Gift)", "Presente do Worlds 26"),
    ("visiting-trainer", "Treinador visitante (só FireRed)", "Treinador da Battle Tower"),
)
_PREFIX = re.compile(r"^[A-Z]+ - ")
_PID_TAG = re.compile(r" \([0-9A-Fa-f]{4,8}\)")
_STATUS = re.compile(r"Mystery Event script status: (\d+)")
_CONSOLE = ("joined",)          # a prova de conceito (Task 2) confirma ou troca este texto


def event_name(path: Path) -> str:
    return _PID_TAG.sub("", _PREFIX.sub("", path.stem)).strip()


def _shiny(d: dict) -> bool:
    tid, sid, pid = d["otid"] & 0xFFFF, d["otid"] >> 16, d["pid"]
    return (tid ^ sid ^ (pid >> 16) ^ (pid & 0xFFFF)) < 8


class Rotation:
    """Qual variante de PID sai na próxima entrega de cada evento (salvo em disco)."""

    def __init__(self, path: Path | None):
        self.path = path
        try:
            self._next = json.loads(path.read_text(encoding="utf-8")) if path else {}
        except (OSError, ValueError):
            self._next = {}

    def next_file(self, event: Event) -> str:
        index = self._next.get(event.key, 0) % len(event.files)
        self._next[event.key] = index + 1
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._next, ensure_ascii=False), encoding="utf-8")
        return event.files[index]


class FrlgAdapter:
    game = "frlg"
    title = "FireRed/LeafGreen"
    mode = "session"
    instructions = "No jogo: MYSTERY GIFT → WONDER CARDS → FRIEND (um console por vez)"

    def __init__(self, rotation_path: Path | None = None):
        self.rotation = Rotation(rotation_path)

    def build_catalog(self, raw_dir: Path, cfg: Config) -> Catalog:
        from distrib.frlg_gift import GiftError, load_mon
        out = cfg.catalog_dir / self.game
        out.mkdir(parents=True, exist_ok=True)
        catalog = Catalog(self.game)
        groups: dict[str, list[tuple[Path, dict]]] = defaultdict(list)
        for path in sorted(raw_dir.rglob("*.pk3")):
            try:
                mon = load_mon(path)
            except GiftError:
                catalog.invalid += 1
                continue
            folder = path.parent.relative_to(raw_dir).as_posix()
            groups[f"{folder}/{event_name(path)}"].append((path, mon.decode()))
        for number, (key, members) in enumerate(sorted(groups.items())):
            files = []
            for variant, (path, _) in enumerate(members):
                name = f"{number:05d}-{variant:03d}.pk3"
                shutil.copyfile(path, out / name)
                files.append(name)
            catalog.events.append(self._event(key, members, tuple(files)))
        for slug, name, description in EXTRAS:
            catalog.events.append(Event(
                game=self.game, key=f"extra:{slug}", name=name, kind="extra",
                details=(("Tipo", "presente do pokeldn"), ("O que faz", description)),
                files=(), sort_key=f"~{name}"))
        save_index(catalog, out / "index.json")
        return catalog

    def _event(self, key: str, members: list, files: tuple[str, ...]) -> Event:
        folder, _, name = key.rpartition("/")
        d = members[0][1]
        shiny = sum(_shiny(m[1]) for m in members)
        details = (("Espécie", d["nickname"]), ("Nível", str(d["level"])),
                   ("OT", d["otName"]), ("TID", str(d["otid"] & 0xFFFF)),
                   ("Idioma", LANGUAGES.get(d["language"], str(d["language"]))),
                   ("Variantes (PID)", str(len(files))),
                   ("Shiny", f"{shiny} de {len(files)} variantes"),
                   ("Pasta", folder))
        return Event(game=self.game, key=key, name=name, kind="pokemon", details=details,
                     files=files, sort_key=name)

    def build_job(self, event: Event, cfg: Config, port: str) -> Job:
        argv = [str(cfg.python), "-u", "-m", "distrib.runners.frlg_session",
                "--pokeldn", str(cfg.pokeldn_dir)]
        if event.kind == "extra":
            argv += ["--extra", event.key.removeprefix("extra:")]
        else:
            argv += ["--pk3", str(cfg.catalog_dir / self.game / self.rotation.next_file(event))]
        argv += ["--keys", str(cfg.keys), "--phy", "auto",
                 "--idle-timeout", str(cfg.frlg_idle_timeout)]
        return Job(argv=tuple(argv), env={"POKELDN_RADIO": f"esp32:{port}"},
                   cwd=str(cfg.project_dir), label=event.name)

    def parse_line(self, line: str) -> Update | None:
        if line.startswith("[distrib] presente "):
            return Update(detail=line.split(": ", 1)[1].strip())
        if line.startswith("Advertising ACTIVITY_WONDER_CARD"):
            return Update(state="on_air")
        if match := _STATUS.search(line):
            code = int(match.group(1))
            return Update(state={2: "delivered", 3: "party_full"}.get(code, "not_delivered"))
        if " delivered. On the Switch" in line:
            return Update(state="delivered")
        if line.startswith("Session finished without delivering anything"):
            return Update(state="not_delivered", detail=line.strip())
        if any(text in line for text in _CONSOLE):
            return Update(state="console")
        if line.startswith(("RuntimeError", "Traceback", "OSError", "PermissionError")):
            return Update(state="error", detail=line.strip())
        return None
```

`distrib/games/__init__.py` (substituir o conteúdo):
```python
from distrib.config import load as _load_config
from distrib.games.frlg import FrlgAdapter
from distrib.games.swsh import SwshAdapter

ADAPTERS = {
    "swsh": SwshAdapter(),
    "frlg": FrlgAdapter(_load_config().state_dir / "rodizio_pid.json"),
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_frlg.py tests/test_swsh.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add distrib/games tests/test_frlg.py
git commit -m "feat(frlg): catálogo .pk3 com rodízio de PID e extras do pokeldn

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Download do Events Gallery e montagem dos catálogos

**Files:**
- Create: `distrib/download.py`, `tests/test_download.py`

**Interfaces:**
- Consumes: `ADAPTERS` e os `build_catalog` (Tasks 4–5), `Config`.
- Produces: `GALLERY_URL: str`; `extract_gallery(stream: BinaryIO, dest: Path, prefixes: tuple[str, ...]) -> int` (quantos arquivos extraídos; aceita tar.gz em fluxo; tira o primeiro componente do caminho, que é `EventsGallery-master/`); `update_catalogs(cfg: Config, games: tuple[str, ...], opener=urllib.request.urlopen, log=print) -> dict[str, Catalog]`.

- [ ] **Step 1: Escrever os testes (falham)**

`tests/test_download.py`:
```python
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
        data = b"x"
        info = tarfile.TarInfo("EventsGallery-master/Released/Gen 3/../../../fora.pk3")
        info.size = 1
        tar.addfile(info, io.BytesIO(data))
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_download.py -v`
Expected: erro de coleta, `ImportError: cannot import name 'download' from 'distrib'`

- [ ] **Step 3: Implementar `distrib/download.py`**

```python
"""Baixa o Events Gallery (tar.gz do GitHub, uma requisição) e remonta os catálogos."""
from __future__ import annotations

import shutil
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from distrib.catalog import Catalog
from distrib.config import Config

GALLERY_URL = "https://codeload.github.com/projectpokemon/EventsGallery/tar.gz/refs/heads/master"
RAW_PREFIX = {"swsh": "Released/Gen 8/SwSh/Wondercards", "frlg": "Released/Gen 3"}
SUFFIX = {"swsh": ".wc8", "frlg": ".pk3"}


def extract_gallery(stream: BinaryIO, dest: Path, prefixes: tuple[str, ...]) -> int:
    count = 0
    with tarfile.open(fileobj=stream, mode="r|gz") as tar:
        for member in tar:
            if not member.isfile():
                continue
            parts = PurePosixPath(member.name).parts[1:]       # tira "EventsGallery-master/"
            if ".." in parts or not parts:
                continue
            rel = PurePosixPath(*parts)
            if not any(rel.as_posix().startswith(p + "/") for p in prefixes):
                continue
            if rel.suffix.lower() not in (".wc8", ".pk3"):
                continue
            target = dest.joinpath(*rel.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            count += 1
    return count


def update_catalogs(cfg: Config, games: tuple[str, ...], opener=urllib.request.urlopen,
                    log=print) -> dict[str, Catalog]:
    from distrib.games import ADAPTERS
    raw = cfg.catalog_dir / "_raw"
    shutil.rmtree(raw, ignore_errors=True)
    log("Baixando o Events Gallery (~56 MB)…")
    with opener(GALLERY_URL, timeout=600) as stream:
        n = extract_gallery(stream, raw, tuple(RAW_PREFIX[g] for g in games))
    log(f"{n} arquivos extraídos.")
    catalogs = {}
    for game in games:
        shutil.rmtree(cfg.catalog_dir / game, ignore_errors=True)
        catalog = ADAPTERS[game].build_catalog(raw / RAW_PREFIX[game], cfg)
        log(f"{ADAPTERS[game].title}: {len(catalog.events)} eventos, {catalog.invalid} inválidos.")
        catalogs[game] = catalog
    shutil.rmtree(raw, ignore_errors=True)
    return catalogs
```

Nota: o `opener` dos testes devolve um `BytesIO`, que serve de gerenciador de contexto (`with`), igual à resposta do `urlopen`.

- [ ] **Step 4: Rodar e ver passar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_download.py -v`
Expected: 3 passed

- [ ] **Step 5: Download real (uma vez, com internet)**

Run: `~/.venvs/pokeldn/bin/python -c "from distrib import config, download; download.update_catalogs(config.load(), ('swsh','frlg'))"`
Expected: `Sword/Shield: 925 eventos, 0 inválidos.` (± alguns, se o Gallery mudou) e `FireRed/LeafGreen: <N> eventos` com N na casa das centenas (os ~3.180 `.pk3` agrupados, mais 10 extras). Anote os números no Step 6.

- [ ] **Step 6: Commit**

```bash
git add distrib/download.py tests/test_download.py
git commit -m "feat: download do Events Gallery e montagem dos catálogos

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Rádio (porta e HELLO) e checagens

**Files:**
- Create: `distrib/radio.py`, `tests/test_radio.py`

**Interfaces:**
- Consumes: `Config`.
- Produces: `PORT_GLOBS = ("/dev/ttyACM*", "/dev/ttyUSB*")`; `find_port(globber=glob.glob) -> str | None` (a única porta; `None` se zero ou mais de uma); `hello(port: str, cfg: Config, run=subprocess.run) -> str` (texto do firmware, ex. `pokeldn-radio esp32 idf=v6.1`; `RadioError` se falhar); `RadioError(Exception)`; `Check` (frozen: `name: str`, `ok: bool`, `message: str`); `run_checks(cfg: Config, catalogs: dict[str, Catalog], find=find_port, hello_fn=hello) -> list[Check]`.

- [ ] **Step 1: Escrever os testes (falham)**

`tests/test_radio.py`:
```python
import subprocess

import pytest

from distrib import radio
from distrib.catalog import Catalog, Event


def test_find_port_single_and_ambiguous():
    assert radio.find_port(lambda pattern: ["/dev/ttyACM0"] if "ACM" in pattern else []) \
        == "/dev/ttyACM0"
    assert radio.find_port(lambda pattern: []) is None
    assert radio.find_port(lambda pattern: ["/dev/ttyACM0", "/dev/ttyACM1"]
                           if "ACM" in pattern else []) is None


def test_hello_ok_and_error(cfg):
    ok = lambda *a, **k: subprocess.CompletedProcess(a, 0, "pokeldn-radio esp32 idf=v6.1\n", "")
    assert radio.hello("/dev/ttyACM0", cfg, run=ok) == "pokeldn-radio esp32 idf=v6.1"
    bad = lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "no reply 0x81\n")
    with pytest.raises(radio.RadioError, match="no reply"):
        radio.hello("/dev/ttyACM0", cfg, run=bad)


def test_hello_timeout(cfg):
    def slow(*a, **k):
        raise subprocess.TimeoutExpired(a, 20)
    with pytest.raises(radio.RadioError, match="não respondeu"):
        radio.hello("/dev/ttyACM0", cfg, run=slow)


def test_run_checks(cfg, tmp_path):
    keys = tmp_path / "prod.keys"
    keys.write_text("x")
    import dataclasses
    cfg = dataclasses.replace(cfg, keys=keys)
    ev = Event("swsh", "k", "n", "pokemon", (), ("f",), "k")
    checks = radio.run_checks(cfg, {"swsh": Catalog("swsh", [ev]), "frlg": Catalog("frlg")},
                              find=lambda: "/dev/ttyACM0", hello_fn=lambda p, c: "idf=v6.1")
    assert [(c.name, c.ok) for c in checks] == [
        ("Placa", True), ("prod.keys", True), ("Sword/Shield", True), ("FireRed/LeafGreen", False)]
    assert "atualizar-catalogo" in checks[3].message


def test_run_checks_no_board(cfg):
    checks = radio.run_checks(cfg, {}, find=lambda: None, hello_fn=None)
    assert checks[0].ok is False
    assert "Plugue a placa" in checks[0].message
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_radio.py -v`
Expected: erro de coleta, `ImportError: cannot import name 'radio' from 'distrib'`

- [ ] **Step 3: Implementar `distrib/radio.py`**

```python
"""A placa: achar a porta serial e fazer o HELLO (num processo filho, como os hosts)."""
from __future__ import annotations

import glob
import subprocess
from dataclasses import dataclass

from distrib.catalog import Catalog
from distrib.config import Config

PORT_GLOBS = ("/dev/ttyACM*", "/dev/ttyUSB*")
TITLES = {"swsh": "Sword/Shield", "frlg": "FireRed/LeafGreen"}
_HELLO = (
    "import sys; sys.path[:0] = [sys.argv[2], sys.argv[2] + '/vendor/LDN'];"
    "from pokeldn.ldn import esp32;"
    "r = esp32.Radio.open_serial(sys.argv[1]);"
    "print(r.hello().text); r.close()"
)


class RadioError(Exception):
    pass


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    message: str


def find_port(globber=glob.glob) -> str | None:
    ports = sorted({p for pattern in PORT_GLOBS for p in globber(pattern)})
    return ports[0] if len(ports) == 1 else None


def hello(port: str, cfg: Config, run=subprocess.run) -> str:
    try:
        done = run([str(cfg.python), "-c", _HELLO, port, str(cfg.pokeldn_dir)],
                   capture_output=True, text=True, timeout=20)
    except subprocess.TimeoutExpired as exc:
        raise RadioError(f"a placa em {port} não respondeu em 20 s") from exc
    if done.returncode != 0:
        last = (done.stderr.strip().splitlines() or ["erro desconhecido"])[-1]
        raise RadioError(f"HELLO falhou em {port}: {last}")
    return done.stdout.strip().splitlines()[-1]


def run_checks(cfg: Config, catalogs: dict[str, Catalog], find=find_port,
               hello_fn=hello) -> list[Check]:
    checks = []
    port = find()
    if port is None:
        checks.append(Check("Placa", False, "Plugue a placa (e confira o usbipd attach) e aperte R"))
    else:
        try:
            checks.append(Check("Placa", True, f"{port}, {hello_fn(port, cfg)}"))
        except RadioError as exc:
            checks.append(Check("Placa", False, f"{exc}. Replugue a placa e aperte R"))
    checks.append(Check("prod.keys", cfg.keys.exists(),
                        "encontrado" if cfg.keys.exists()
                        else f"não encontrado em {cfg.keys}; veja docs/instalacao.md"))
    for game, title in TITLES.items():
        catalog = catalogs.get(game) or Catalog(game)
        n = len(catalog.events)
        checks.append(Check(title, n > 0,
                            f"{n} eventos" if n else
                            "catálogo vazio: rode 'python -m distrib atualizar-catalogo'"))
    return checks
```

- [ ] **Step 4: Rodar e ver passar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_radio.py -v`
Expected: 5 passed

- [ ] **Step 5: Conferir com a placa de verdade**

Run: `~/.venvs/pokeldn/bin/python -c "from distrib import radio, config; p = radio.find_port(); print(p, radio.hello(p, config.load()))"`
Expected: `/dev/ttyACM0 pokeldn-radio esp32 idf=v6.1` (se der "Permission denied" como usuário comum, rode no terminal com o grupo `dialout` ou como root).

- [ ] **Step 6: Commit**

```bash
git add distrib/radio.py tests/test_radio.py
git commit -m "feat: detecção da placa, HELLO e checagens de início

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Supervisor do host (`distributor.py`)

**Files:**
- Create: `distrib/distributor.py`, `tests/fake_host.py`, `tests/test_distributor.py`

**Interfaces:**
- Consumes: `Job`, `Update`, `Adapter.parse_line`, `Adapter.mode` (Task 4).
- Produces:
  - `Status` (dataclass, cópia imutável entregue a quem lê): `state: str` (`"idle"`, `"starting"`, `"on_air"`, `"console"`, `"no_board"`, `"failed"`, `"paused"`), `label: str`, `since: float | None` (quando entrou no ar), `channel: int | None`, `restarts: int`, `deliveries: int`, `last_event: str` (último "entregue"/"equipe cheia"/…), `detail: str`.
  - `Distributor(mode: str, parse_line: Callable[[str], Update | None], job_factory: Callable[[str], Job], log_path: Path, find_port: Callable[[], str | None], max_failures: int = 3, retry_delay: float = 3.0, clock=time.monotonic)`: `start()`, `stop()` (mata e espera o processo), `pause()`, `resume()`, `status() -> Status`, `running: bool`.
  - Regras: `job_factory(port)` é chamado a cada (re)início; sem porta → `no_board` e nova tentativa após `retry_delay`, **sem** contar falha. `broadcast`: saída do processo = falha (+1, `restarts` +1); `on_air` zera as falhas seguidas. `session`: saída 0 = entregue (`deliveries` +1), 1 = não entregue, 124 = ninguém veio (nenhuma dessas conta como falha, e o host reinicia na hora); outras saídas = falha. Depois de `max_failures` falhas seguidas → `failed` (para). Cada linha vai para o log com a hora.

- [ ] **Step 1: O host falso**

`tests/fake_host.py`:
```python
"""Imita um host: imprime o roteiro passado em argv e sai com o código dado.

    python tests/fake_host.py EXIT_CODE 'linha 1' 'sleep:0.2' 'linha 2' ...
"""
import sys
import time

code, *script = sys.argv[1:]
for item in script:
    if item.startswith("sleep:"):
        time.sleep(float(item[6:]))
    else:
        print(item, flush=True)
sys.exit(int(code))
```

- [ ] **Step 2: Escrever os testes (falham)**

`tests/test_distributor.py`:
```python
import sys
import time
from pathlib import Path

from distrib.distributor import Distributor
from distrib.games.base import Job, Update
from distrib.games.frlg import FrlgAdapter
from distrib.games.swsh import SwshAdapter

FAKE = str(Path(__file__).parent / "fake_host.py")


def job(code, *script):
    return lambda port: Job(argv=(sys.executable, FAKE, str(code), *script), label="Teste")


def wait_for(pred, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.02)
    return False


def make(tmp_path, mode, factory, find=lambda: "/dev/ttyACM0", **kw):
    parse = SwshAdapter().parse_line if mode == "broadcast" else FrlgAdapter(None).parse_line
    return Distributor(mode, parse, factory, tmp_path / "log.txt", find,
                       retry_delay=0.05, **kw)


def test_broadcast_goes_on_air(tmp_path):
    d = make(tmp_path, "broadcast", job(0, "[host] AP up: ssid=x ch=6 us=y",
                                        "advertising comm id 0x1", "sleep:5"))
    d.start()
    assert wait_for(lambda: d.status().state == "on_air")
    st = d.status()
    assert st.channel == 6 and st.label == "Teste" and st.since is not None
    d.stop()
    assert d.status().state == "idle"
    assert "advertising comm id" in (tmp_path / "log.txt").read_text(encoding="utf-8")


def test_broadcast_restarts_then_gives_up(tmp_path):
    d = make(tmp_path, "broadcast", job(1, "RuntimeError: LDN host bring-up failed"))
    d.start()
    assert wait_for(lambda: d.status().state == "failed")
    st = d.status()
    assert st.restarts == 3
    assert "bring-up failed" in st.detail
    d.stop()


def test_on_air_resets_failure_streak(tmp_path):
    calls = []

    def factory(port):
        calls.append(port)
        if len(calls) % 2:
            return job(1, "RuntimeError: x")(port)
        return job(1, "advertising comm id 0x1", "sleep:0.1")(port)

    d = make(tmp_path, "broadcast", factory)
    d.start()
    assert wait_for(lambda: len(calls) >= 8)
    assert d.status().state != "failed"
    d.stop()


def test_session_counts_deliveries_and_restarts(tmp_path):
    d = make(tmp_path, "session", job(0, "Advertising ACTIVITY_WONDER_CARD.",
                                      "Mystery Event script status: 2 (success)"))
    d.start()
    assert wait_for(lambda: d.status().deliveries >= 3)
    st = d.status()
    assert st.state != "failed" and st.last_event == "entregue"
    d.stop()


def test_session_idle_timeout_is_not_a_failure(tmp_path):
    d = make(tmp_path, "session", job(124, "Advertising ACTIVITY_WONDER_CARD."))
    d.start()
    time.sleep(0.6)
    assert d.status().state != "failed"
    d.stop()


def test_session_party_full(tmp_path):
    d = make(tmp_path, "session", job(1, "Advertising ACTIVITY_WONDER_CARD.",
                                      "Mystery Event script status: 3 (incompatible)"))
    d.start()
    assert wait_for(lambda: d.status().last_event == "equipe cheia")
    assert d.status().deliveries == 0
    d.stop()


def test_no_board_waits_without_counting_failures(tmp_path):
    present = {"port": None}
    d = make(tmp_path, "broadcast", job(0, "advertising comm id 0x1", "sleep:5"),
             find=lambda: present["port"])
    d.start()
    assert wait_for(lambda: d.status().state == "no_board")
    time.sleep(0.3)
    assert d.status().restarts == 0
    present["port"] = "/dev/ttyACM0"
    assert wait_for(lambda: d.status().state == "on_air")
    d.stop()


def test_switch_stops_previous_process_first(tmp_path):
    d1 = make(tmp_path, "broadcast", job(0, "advertising comm id 0x1", "sleep:30"))
    d1.start()
    assert wait_for(lambda: d1.status().state == "on_air")
    proc = d1._proc
    d1.stop()
    assert proc.poll() is not None
    assert not d1.running


def test_pause_and_resume(tmp_path):
    d = make(tmp_path, "broadcast", job(0, "advertising comm id 0x1", "sleep:30"))
    d.start()
    assert wait_for(lambda: d.status().state == "on_air")
    d.pause()
    assert d.status().state == "paused"
    d.resume()
    assert wait_for(lambda: d.status().state == "on_air")
    d.stop()
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_distributor.py -v`
Expected: erro de coleta, `ModuleNotFoundError: No module named 'distrib.distributor'`

- [ ] **Step 4: Implementar `distrib/distributor.py`**

```python
"""Mantém o host no ar: sobe o processo, lê o log, reinicia quando cai. Nada de interface."""
from __future__ import annotations

import os
import subprocess
import threading
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Callable

from distrib.games.base import Job, Update

EVENT_TEXT = {"delivered": "entregue", "party_full": "equipe cheia",
              "not_delivered": "não entregue"}


@dataclass(frozen=True)
class Status:
    state: str = "idle"
    label: str = ""
    since: float | None = None
    channel: int | None = None
    restarts: int = 0
    deliveries: int = 0
    last_event: str = ""
    detail: str = ""


class Distributor:
    def __init__(self, mode: str, parse_line: Callable[[str], Update | None],
                 job_factory: Callable[[str], Job], log_path: Path,
                 find_port: Callable[[], str | None], max_failures: int = 3,
                 retry_delay: float = 3.0, clock=time.monotonic):
        self.mode, self.parse_line, self.job_factory = mode, parse_line, job_factory
        self.log_path, self.find_port = log_path, find_port
        self.max_failures, self.retry_delay, self.clock = max_failures, retry_delay, clock
        self._lock = threading.Lock()
        self._status = Status()
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._thread: threading.Thread | None = None
        self._proc: subprocess.Popen | None = None

    # ---- API ----
    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def status(self) -> Status:
        with self._lock:
            return self._status

    def start(self) -> None:
        self.stop()
        self._stop.clear()
        self._paused.clear()
        self._set(state="starting", restarts=0, deliveries=0, last_event="", detail="")
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._kill()
        if self._thread is not None:
            self._thread.join(timeout=15)
            self._thread = None
        self._set(state="idle", since=None, channel=None)

    def pause(self) -> None:
        self._paused.set()
        self._kill()
        self._set(state="paused", since=None)

    def resume(self) -> None:
        self._paused.clear()
        self._set(state="starting")

    # ---- interno ----
    def _set(self, **changes) -> None:
        with self._lock:
            self._status = replace(self._status, **changes)

    def _log(self, line: str) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%H:%M:%S} {line}\n")

    def _kill(self) -> None:
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    def _loop(self) -> None:
        failures = 0
        while not self._stop.is_set():
            if self._paused.is_set():
                time.sleep(0.05)
                continue
            port = self.find_port()
            if port is None:
                self._set(state="no_board", since=None)
                self._stop.wait(self.retry_delay)
                continue
            job = self.job_factory(port)
            self._set(state="starting", label=job.label, channel=None)
            self._log(f"=== início: {job.label} ({port})")
            reached_air = self._run(job)
            if self._stop.is_set() or self._paused.is_set():
                continue
            code = self._proc.returncode
            self._log(f"=== fim: código {code}")
            if reached_air:
                failures = 0
            if self.mode == "session" and code in (0, 1, 124):
                continue                    # sessão terminou normalmente; próximo console
            failures += 1
            self._set(restarts=self.status().restarts + 1)
            if failures >= self.max_failures:
                self._set(state="failed", since=None)
                return
            self._stop.wait(self.retry_delay)

    def _run(self, job: Job) -> bool:
        env = {**os.environ, **job.env}
        self._proc = subprocess.Popen(job.argv, cwd=job.cwd, env=env, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, text=True, bufsize=1)
        reached_air = False
        for line in self._proc.stdout:
            line = line.rstrip("\n")
            self._log(line)
            update = self.parse_line(line)
            if update is None:
                continue
            changes = {}
            if update.channel is not None:
                changes["channel"] = update.channel
            if update.detail is not None:
                changes["detail"] = update.detail
            if update.state == "on_air":
                reached_air = True
                changes.update(state="on_air", since=self.status().since or self.clock())
            elif update.state == "console":
                changes["state"] = "console"
            elif update.state in EVENT_TEXT:
                changes["last_event"] = EVENT_TEXT[update.state]
                if update.state == "delivered":
                    changes["deliveries"] = self.status().deliveries + 1
            self._set(**changes)
        self._proc.wait()
        return reached_air
```

- [ ] **Step 5: Rodar e ver passar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_distributor.py -v`
Expected: 9 passed. Se `test_session_counts_deliveries_and_restarts` passar do ponto por ser rápido demais, está certo: o host falso sai na hora e o supervisor reinicia na hora.

- [ ] **Step 6: Commit**

```bash
git add distrib/distributor.py tests/fake_host.py tests/test_distributor.py
git commit -m "feat: supervisor do host (reinício, sessões, placa ausente, pausa)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: TUI parte 1: serviços, checagem, jogo e catálogo

**Files:**
- Create: `distrib/app.py`, `tests/test_app.py`

**Interfaces:**
- Consumes: `Config`, `Catalog`, `load_index`, `Favorites` (Task 3), `ADAPTERS` (Tasks 4–5), `run_checks`, `Check`, `find_port` (Task 7), `Distributor`, `Status` (Task 8).
- Produces:
  - `Services` (dataclass): `cfg: Config`, `adapters: dict`, `catalogs: dict[str, Catalog]`, `favorites: Favorites`, `checks: Callable[[], list[Check]]`, `make_distributor: Callable[[Adapter, Event], Distributor]`.
  - `default_services(cfg: Config) -> Services`.
  - `DistribApp(services: Services)` (Textual `App`), telas `CheckScreen`, `GameScreen`, `CatalogScreen(adapter, on_pick)`. `OnAirScreen` vem na Task 10; aqui o `Enter` do catálogo chama `app.distribute(adapter, event)`, que a Task 10 implementa. Nesta task, `distribute` só guarda `self.last_pick = (game, key)`.

- [ ] **Step 1: Escrever os testes (falham)**

`tests/test_app.py`:
```python
import asyncio

from distrib.app import CatalogScreen, CheckScreen, DistribApp, GameScreen, Services
from distrib.catalog import Catalog, Event, Favorites
from distrib.games.frlg import FrlgAdapter
from distrib.games.swsh import SwshAdapter
from distrib.radio import Check


def ev(game, key, name, kind="pokemon"):
    return Event(game, key, name, kind, (("Espécie", "#893"), ("Nível", "60")), (f"{key}.x",), key)


def services(tmp_path, checks_ok=True, distributor=None):
    catalogs = {
        "swsh": Catalog("swsh", [ev("swsh", "a", "Jungle Zarude"),
                                 ev("swsh", "b", "Item Poke Ball x100", "item"),
                                 ev("swsh", "c", "Shiny Celebi")]),
        "frlg": Catalog("frlg", [ev("frlg", "x", "10ANNIV Lugia (ENG)")]),
    }
    return Services(
        cfg=None, adapters={"swsh": SwshAdapter(), "frlg": FrlgAdapter(None)},
        catalogs=catalogs, favorites=Favorites(tmp_path / "fav.json"),
        checks=lambda: [Check("Placa", checks_ok, "ok" if checks_ok else "Plugue a placa")],
        make_distributor=lambda adapter, event: distributor)


def run(coro):
    return asyncio.run(coro)


def test_check_screen_blocks_until_ok(tmp_path):
    async def go():
        app = DistribApp(services(tmp_path, checks_ok=False))
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, CheckScreen)
            await pilot.press("enter")
            assert isinstance(app.screen, CheckScreen)
    run(go())


def test_flow_to_catalog_and_search(tmp_path):
    async def go():
        app = DistribApp(services(tmp_path))
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")                  # checagem ok -> jogos
            assert isinstance(app.screen, GameScreen)
            await pilot.press("enter")                  # Sword/Shield
            assert isinstance(app.screen, CatalogScreen)
            assert app.screen.visible_keys() == ["a", "c"]
            await pilot.press(*"celebi")
            await pilot.pause()
            assert app.screen.visible_keys() == ["c"]
            await pilot.press("enter")                  # Enter na busca foca a lista
            assert app.screen.focused.id == "lista"
    run(go())


def test_items_toggle_and_favorites_first(tmp_path):
    async def go():
        s = services(tmp_path)
        app = DistribApp(s)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter", "enter")
            screen = app.screen
            screen.query_one("#lista").focus()
            await pilot.press("i")
            assert screen.visible_keys() == ["a", "b", "c"]
            await pilot.press("down")                   # segundo item
            await pilot.press("f")
            await pilot.pause()
            assert screen.visible_keys()[0] == screen.favorite_keys()[0]
            assert len(screen.favorite_keys()) == 1
    run(go())


def test_enter_on_event_calls_distribute(tmp_path):
    async def go():
        app = DistribApp(services(tmp_path))
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter", "down", "enter")   # FireRed/LeafGreen
            screen = app.screen
            screen.query_one("#lista").focus()
            await pilot.press("enter")
            await pilot.pause()
            assert app.last_pick == ("frlg", "x")
    run(go())
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_app.py -v`
Expected: erro de coleta, `ModuleNotFoundError: No module named 'distrib.app'`

- [ ] **Step 3: Implementar `distrib/app.py` (parte 1)**

```python
"""As telas (Textual). Só conversam com o catálogo, o distributor e as checagens."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, OptionList, Static
from textual.widgets.option_list import Option

from distrib.catalog import Catalog, Event, Favorites, load_index
from distrib.config import Config


@dataclass
class Services:
    cfg: Config | None
    adapters: dict
    catalogs: dict[str, Catalog]
    favorites: Favorites
    checks: Callable[[], list]
    make_distributor: Callable


def default_services(cfg: Config) -> Services:
    from distrib import radio
    from distrib.distributor import Distributor
    from distrib.games import ADAPTERS
    catalogs = {g: load_index(g, cfg.catalog_dir / g / "index.json") for g in ADAPTERS}

    def make_distributor(adapter, event):
        log = cfg.logs_dir / f"{date.today():%Y-%m-%d}.log"
        return Distributor(adapter.mode, adapter.parse_line,
                           lambda port: adapter.build_job(event, cfg, port), log,
                           radio.find_port, max_failures=3)

    return Services(cfg, ADAPTERS, catalogs, Favorites(cfg.state_dir / "favoritos.json"),
                    lambda: radio.run_checks(cfg, catalogs), make_distributor)


class CheckScreen(Screen):
    BINDINGS = [Binding("enter", "go", "Continuar"), Binding("r", "recheck", "Checar de novo"),
                Binding("q", "app.quit", "Sair")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Checando…", id="checks")
        yield Footer()

    def on_mount(self) -> None:
        self.action_recheck()

    def action_recheck(self) -> None:
        self.results = self.app.services.checks()
        lines = [f"{'✓' if c.ok else '✗'} {c.name}: {c.message}" for c in self.results]
        self.query_one("#checks", Static).update("\n".join(lines))

    def action_go(self) -> None:
        if all(c.ok for c in self.results if c.name in ("Placa", "prod.keys")):
            self.app.push_screen(GameScreen())
        else:
            self.notify("Resolva a placa e o prod.keys antes de continuar.", severity="error")


class GameScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Voltar"), Binding("q", "app.quit", "Sair")]

    def compose(self) -> ComposeResult:
        yield Header()
        options = []
        for game, adapter in self.app.services.adapters.items():
            n = len(self.app.services.catalogs.get(game, Catalog(game)).events)
            options.append(Option(f"{adapter.title}  ({n} eventos)", id=game))
        yield OptionList(*options, id="jogos")
        yield Footer()

    def on_option_list_option_selected(self, message: OptionList.OptionSelected) -> None:
        game = message.option.id
        self.app.push_screen(CatalogScreen(self.app.services.adapters[game]))


class CatalogScreen(Screen):
    BINDINGS = [Binding("f", "favorite", "Vitrine"), Binding("i", "items", "Itens/BP"),
                Binding("escape", "app.pop_screen", "Voltar")]

    def __init__(self, adapter):
        super().__init__()
        self.adapter = adapter
        self.catalog: Catalog = None
        self.include_items = False
        self._shown: list[Event] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder="Buscar (nome, espécie, OT)…", id="busca")
        with Horizontal():
            yield OptionList(id="lista")
            yield Static("", id="detalhes")
        yield Footer()

    def on_mount(self) -> None:
        self.catalog = self.app.services.catalogs[self.adapter.game]
        self.title = self.adapter.title
        self.refresh_list()

    def favorite_keys(self) -> list[str]:
        fav = self.app.services.favorites
        return [e.key for e in self._shown if fav.contains(e)]

    def visible_keys(self) -> list[str]:
        return [e.key for e in self._shown]

    def refresh_list(self) -> None:
        text = self.query_one("#busca", Input).value
        found = self.catalog.search(text, include_items=self.include_items)
        fav = self.app.services.favorites
        self._shown = [e for e in found if fav.contains(e)] + \
                      [e for e in found if not fav.contains(e)]
        lista = self.query_one("#lista", OptionList)
        highlighted = lista.highlighted
        lista.clear_options()
        lista.add_options([Option(("★ " if fav.contains(e) else "  ") + e.name, id=e.key)
                           for e in self._shown])
        if self._shown:
            lista.highlighted = min(highlighted or 0, len(self._shown) - 1)
        self.show_details()

    def current(self) -> Event | None:
        lista = self.query_one("#lista", OptionList)
        if lista.highlighted is None or not self._shown:
            return None
        return self._shown[lista.highlighted]

    def show_details(self) -> None:
        event = self.current()
        text = "" if event is None else event.name + "\n\n" + "\n".join(
            f"{label}: {value}" for label, value in event.details)
        self.query_one("#detalhes", Static).update(text)

    def on_input_changed(self, message: Input.Changed) -> None:
        self.refresh_list()

    def on_input_submitted(self, message: Input.Submitted) -> None:
        self.query_one("#lista", OptionList).focus()     # Enter na busca vai para a lista

    def on_option_list_option_highlighted(self, message: OptionList.OptionHighlighted) -> None:
        self.show_details()

    def on_option_list_option_selected(self, message: OptionList.OptionSelected) -> None:
        event = self.catalog.get(message.option.id)
        self.app.distribute(self.adapter, event)

    def action_favorite(self) -> None:
        event = self.current()
        if event is not None:
            self.app.services.favorites.toggle(event)
            self.refresh_list()

    def action_items(self) -> None:
        self.include_items = not self.include_items
        self.refresh_list()


class DistribApp(App):
    TITLE = "Distribuidor de Eventos — pokeldn"
    CSS = """
    #lista { width: 1fr; }
    #detalhes { width: 1fr; padding: 1 2; border: round $accent; }
    #checks { padding: 1 2; }
    """

    def __init__(self, services: Services):
        super().__init__()
        self.services = services
        self.last_pick: tuple[str, str] | None = None

    def on_mount(self) -> None:
        self.push_screen(CheckScreen())

    def distribute(self, adapter, event: Event) -> None:
        self.last_pick = (adapter.game, event.key)
```

Observação para quem implementa: dentro do `CatalogScreen`, as letras digitadas vão para o `Input` quando ele tem o foco (é o caso ao abrir a tela), por isso os testes focam a `#lista` antes de apertar `f`/`i`/`enter`.

- [ ] **Step 4: Rodar e ver passar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_app.py -v`
Expected: 4 passed. Se um nome da API da Textual 8.2.8 divergir (por exemplo, `OptionList.OptionSelected`), consulte a doc da versão fixada (context7 `textual`) e ajuste a chamada, não o teste.

- [ ] **Step 5: Commit**

```bash
git add distrib/app.py tests/test_app.py
git commit -m "feat(tui): checagem, escolha do jogo e catálogo com busca e vitrine

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: TUI parte 2: tela "No ar"

**Files:**
- Modify: `distrib/app.py` (acrescentar `OnAirScreen`, `format_status`, trocar `DistribApp.distribute`)
- Modify: `tests/test_app.py` (acrescentar testes)

**Interfaces:**
- Consumes: `Status`, `Distributor` (Task 8); `Adapter.mode`, `Adapter.instructions` (Tasks 4–5).
- Produces: `format_status(status: Status, mode: str, now: float) -> str`; `OnAirScreen(adapter, event, distributor)`; `DistribApp.distribute(adapter, event)`, que para o distributor atual (se houver), cria outro por `services.make_distributor`, inicia e mostra a `OnAirScreen`. Tecla `t` volta ao catálogo **sem** parar o atual; um novo `Enter` troca o evento. `p` alterna pausa. `q` para tudo e sai.

- [ ] **Step 1: Escrever os testes (falham)**

Acrescentar a `tests/test_app.py`:
```python
from distrib.app import OnAirScreen, format_status
from distrib.distributor import Status


class FakeDistributor:
    def __init__(self):
        self.calls = []
        self._status = Status(state="on_air", label="Jungle Zarude", since=0.0, channel=11)

    def start(self): self.calls.append("start")
    def stop(self): self.calls.append("stop")
    def pause(self): self.calls.append("pause"); self._status = Status(state="paused")
    def resume(self): self.calls.append("resume")
    def status(self): return self._status


def test_format_status_broadcast():
    text = format_status(Status(state="on_air", label="Jungle Zarude", since=0.0, channel=11,
                                restarts=1), "broadcast", now=754.0)
    assert "● NO AR há 12:34" in text
    assert "Jungle Zarude" in text and "Canal 11" in text and "reinícios: 1" in text


def test_format_status_session_and_problems():
    text = format_status(Status(state="on_air", label="10ANNIV Lugia", since=0.0, deliveries=3,
                                last_event="equipe cheia", detail="LUGIA Nv70"), "session", 10.0)
    assert "AGUARDANDO CONSOLE" in text and "Entregas: 3" in text
    assert "equipe cheia" in text and "liberar um espaço" in text
    assert "placa desconectada" in format_status(Status(state="no_board"), "broadcast", 0.0)
    failed = format_status(Status(state="failed", detail="RuntimeError: x"), "broadcast", 0.0)
    assert "PAROU" in failed and "RuntimeError: x" in failed


def test_distribute_switch_pause_quit(tmp_path):
    first, second = FakeDistributor(), FakeDistributor()
    made = [first, second]

    async def go():
        s = services(tmp_path)
        s.make_distributor = lambda adapter, event: made.pop(0)
        app = DistribApp(s)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter", "enter")
            app.screen.query_one("#lista").focus()
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, OnAirScreen)
            assert first.calls == ["start"]
            await pilot.press("p")
            assert first.calls[-1] == "pause"
            await pilot.press("p")
            assert first.calls[-1] == "resume"
            await pilot.press("t")                      # volta ao catálogo, sem parar
            await pilot.pause()
            assert isinstance(app.screen, CatalogScreen) and "stop" not in first.calls
            app.screen.query_one("#lista").focus()
            await pilot.press("down", "enter")          # outro evento
            await pilot.pause()
            assert first.calls[-1] == "stop" and second.calls == ["start"]
            await pilot.press("q")
            await pilot.pause()
            assert second.calls[-1] == "stop"
    run(go())
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_app.py -v`
Expected: `ImportError: cannot import name 'OnAirScreen' from 'distrib.app'`

- [ ] **Step 3: Implementar em `distrib/app.py`**

Acrescentar os imports `import time` e `from distrib.distributor import Status`. Acrescentar antes de `class DistribApp`:
```python
def format_status(status: Status, mode: str, now: float) -> str:
    if status.state == "no_board":
        return "⚠ placa desconectada: replugue a placa; volto sozinho quando ela aparecer"
    if status.state == "failed":
        return ("✗ PAROU depois de 3 falhas seguidas\n"
                f"Último erro: {status.detail or '(veja o log em logs/)'}\n"
                "Aperte T para escolher de novo ou Q para sair.")
    if status.state == "paused":
        return "⏸ PAUSADO: aperte P para voltar"
    if status.state == "starting":
        head = "… subindo o host"
    elif mode == "session":
        head = "● CONSOLE CONECTADO" if status.state == "console" else "● AGUARDANDO CONSOLE"
    else:
        elapsed = int(now - status.since) if status.since is not None else 0
        head = f"● NO AR há {elapsed // 60:02d}:{elapsed % 60:02d}"
    lines = [head, status.label]
    if mode == "session":
        lines.append(f"Entregas: {status.deliveries}")
        if status.detail:
            lines.append(f"Última: {status.detail}")
        if status.last_event:
            lines.append(f"Resultado da última sessão: {status.last_event}")
        if status.last_event == "equipe cheia":
            lines.append("→ peça para o jogador liberar um espaço na equipe e tentar de novo")
    else:
        lines.append(f"Canal {status.channel or '?'} · reinícios: {status.restarts}")
    return "\n".join(lines)


class OnAirScreen(Screen):
    BINDINGS = [Binding("t", "switch", "Trocar evento"), Binding("p", "pause", "Pausar"),
                Binding("q", "quit_all", "Sair")]

    def __init__(self, adapter, event: Event, distributor):
        super().__init__()
        self.adapter, self.event, self.distributor = adapter, event, distributor

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("", id="estado")
            yield Static(self.adapter.instructions, id="instrucoes")
        yield Footer()

    def on_mount(self) -> None:
        self.tick()
        self.set_interval(0.5, self.tick)

    def tick(self) -> None:
        text = format_status(self.distributor.status(), self.adapter.mode, time.monotonic())
        self.query_one("#estado", Static).update(text)

    def action_switch(self) -> None:
        self.app.pop_screen()

    def action_pause(self) -> None:
        if self.distributor.status().state == "paused":
            self.distributor.resume()
        else:
            self.distributor.pause()
        self.tick()

    def action_quit_all(self) -> None:
        self.app.stop_distribution()
        self.app.exit()
```

Em `DistribApp`, acrescentar `self.distributor = None` no `__init__` e substituir `distribute`:
```python
    def distribute(self, adapter, event: Event) -> None:
        self.last_pick = (adapter.game, event.key)
        self.stop_distribution()
        self.distributor = self.services.make_distributor(adapter, event)
        self.distributor.start()
        if isinstance(self.screen, OnAirScreen):
            self.pop_screen()
        self.push_screen(OnAirScreen(adapter, event, self.distributor))

    def stop_distribution(self) -> None:
        if self.distributor is not None:
            self.distributor.stop()
            self.distributor = None

    def on_unmount(self) -> None:
        self.stop_distribution()
```

O teste antigo `test_enter_on_event_calls_distribute` usa `make_distributor=lambda …: None`. Troque, em `services()`, o padrão por `distributor or FakeDistributor()` (mova a classe `FakeDistributor` para o topo do arquivo de teste).

- [ ] **Step 4: Rodar e ver passar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_app.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add distrib/app.py tests/test_app.py
git commit -m "feat(tui): tela No ar com troca de evento, pausa e estados de erro

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Linha de comando (`python -m distrib`)

**Files:**
- Create: `distrib/__main__.py`, `tests/test_main.py`

**Interfaces:**
- Consumes: `config.load`, `download.update_catalogs`, `app.DistribApp`, `app.default_services`, `radio.run_checks`, `pokeldn_path.ensure_importable`.
- Produces: `main(argv: list[str] | None = None) -> int` com os subcomandos `tui` (padrão), `atualizar-catalogo [swsh|frlg]` e `checar` (imprime as checagens; código 0 se placa e keys ok, 1 se não).

- [ ] **Step 1: Escrever os testes (falham)**

`tests/test_main.py`:
```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `~/.venvs/pokeldn/bin/python -m pytest tests/test_main.py -v`
Expected: `ImportError`/`AttributeError`: `distrib.__main__` sem `main`

- [ ] **Step 3: Implementar `distrib/__main__.py`**

```python
"""python -m distrib [tui | atualizar-catalogo [swsh|frlg] | checar]"""
from __future__ import annotations

import argparse
import sys

from distrib import config as configmod
from distrib.pokeldn_path import ensure_importable


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m distrib")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("tui", help="abre a interface (padrão)")
    up = sub.add_parser("atualizar-catalogo", help="baixa o Events Gallery e remonta os catálogos")
    up.add_argument("jogos", nargs="*", choices=("swsh", "frlg"))
    sub.add_parser("checar", help="confere placa, prod.keys e catálogos")
    args = parser.parse_args(argv)
    cfg = configmod.load()
    ensure_importable(cfg.pokeldn_dir)

    if args.cmd == "atualizar-catalogo":
        from distrib import download
        download.update_catalogs(cfg, tuple(args.jogos or ("swsh", "frlg")))
        return 0

    from distrib.app import default_services
    services = default_services(cfg)
    if args.cmd == "checar":
        from distrib import radio
        checks = radio.run_checks(cfg, services.catalogs)
        for check in checks:
            print(f"{'✓' if check.ok else '✗'} {check.name}: {check.message}")
        return 0 if all(c.ok for c in checks if c.name in ("Placa", "prod.keys")) else 1

    from distrib.app import DistribApp
    DistribApp(services).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Rodar a suíte inteira**

Run: `~/.venvs/pokeldn/bin/python -m pytest -v`
Expected: todos passam (config 3, frlg_gift 6, catálogo 7, swsh 6, frlg 7, download 3, radio 5, distributor 9, app 7, main 2 = 55)

- [ ] **Step 5: Conferir de verdade, com a placa**

Run (do Windows): `wsl.exe -u root -- bash -lc 'cd /mnt/c/Gabry/Projects/pokeldn-distrib && DISTRIB_USER_HOME=/home/gabryel /home/gabryel/.venvs/pokeldn/bin/python -m distrib checar'`
Expected: `✓ Placa: /dev/ttyACM0, pokeldn-radio esp32 idf=v6.1`, `✓ prod.keys: encontrado`, `✓ Sword/Shield: … eventos`, `✓ FireRed/LeafGreen: … eventos`.

- [ ] **Step 6: Commit**

```bash
git add distrib/__main__.py tests/test_main.py
git commit -m "feat: linha de comando (tui, atualizar-catalogo, checar)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Launcher do Windows (WSL + usbipd + TUI como root)

**Files:**
- Create: `windows/iniciar.ps1`, `windows/usb.ps1`, `Iniciar Distribuicao.bat`, `windows/tests/usb.Tests.ps1`

**Interfaces:**
- Produces: `windows/usb.ps1` com `Get-BoardBusId([string[]] $UsbipdListLines) -> @{BusId; State}` ou `$null`; IDs aceitos: `1a86:55d4` (CH9102), `10c4:ea60` (CP2102), `1a86:7523` (CH340). `iniciar.ps1` usa isso, mantém o WSL vivo, faz o attach (e um laço de re-attach a cada 5 s enquanto a TUI roda) e abre `python -m distrib` como root com `DISTRIB_USER_HOME`.

- [ ] **Step 1: Escrever o teste da leitura do `usbipd list` (falha)**

`windows/tests/usb.Tests.ps1` (roda sem Pester, com asserções simples):
```powershell
. "$PSScriptRoot\..\usb.ps1"
$ok = 0; $fail = 0
function Assert-Eq($got, $want, $name) {
    if ($got -eq $want) { $script:ok++ } else { $script:fail++; Write-Host "FALHOU $name : '$got' != '$want'" }
}
$lines = @(
  'Connected:',
  'BUSID  VID:PID    DEVICE                                                        STATE',
  '1-4    0d8c:0005  Blue Snowball, Dispositivo de Entrada USB                     Not shared',
  '1-6    1a86:55d4  Dispositivo Serial USB (COM4)                                 Shared',
  '',
  'Persisted:'
)
$b = Get-BoardBusId $lines
Assert-Eq $b.BusId '1-6' 'busid'
Assert-Eq $b.State 'Shared' 'state'
$b = Get-BoardBusId @('1-5    10c4:ea60  CP2102 USB to UART Bridge Controller (COM3)   Attached')
Assert-Eq $b.State 'Attached' 'cp2102 attached'
$b = Get-BoardBusId @('1-5    10c4:ea60  CP2102 USB to UART Bridge Controller (COM3)   Not shared')
Assert-Eq $b.State 'Not shared' 'not shared'
Assert-Eq (Get-BoardBusId @('1-4    0d8c:0005  Blue Snowball   Not shared')) $null 'sem placa'
Write-Host "$ok ok, $fail falhas"
if ($fail) { exit 1 }
```

- [ ] **Step 2: Rodar e ver falhar**

Run (PowerShell): `powershell -NoProfile -ExecutionPolicy Bypass -File windows\tests\usb.Tests.ps1`
Expected: erro "usb.ps1 não encontrado" / `Get-BoardBusId` não reconhecido

- [ ] **Step 3: Implementar `windows/usb.ps1`**

```powershell
# Leitura do "usbipd list": acha a placa ESP32 pelos VID:PID das pontes USB conhecidas.
$BoardIds = @('1a86:55d4', '10c4:ea60', '1a86:7523')   # CH9102, CP2102, CH340

function Get-BoardBusId([string[]] $UsbipdListLines) {
    foreach ($line in $UsbipdListLines) {
        if ($line -match '^(?<bus>\d+-\d+)\s+(?<id>[0-9a-f]{4}:[0-9a-f]{4})\s+.*?\s(?<state>Not shared|Shared|Attached)\s*$') {
            if ($BoardIds -contains $Matches.id) {
                return @{ BusId = $Matches.bus; State = $Matches.state }
            }
        }
    }
    return $null
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File windows\tests\usb.Tests.ps1`
Expected: `5 ok, 0 falhas`

- [ ] **Step 5: `windows/iniciar.ps1` e o `.bat`**

`windows/iniciar.ps1`:
```powershell
# Prepara o Windows e abre o Distribuidor de Eventos como root no WSL.
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\usb.ps1"
$project = Split-Path $PSScriptRoot -Parent

function Fail($msg) { Write-Host "`n$msg" -ForegroundColor Red; Read-Host 'Enter para fechar'; exit 1 }

if (-not (Get-Command usbipd -ErrorAction SilentlyContinue)) {
    Fail 'usbipd não está instalado. Rode windows\instalar.ps1 (veja docs\instalacao.md).'
}
# O usbipd attach exige uma distro do WSL rodando: deixamos uma sessão aberta em segundo plano.
$keep = Start-Process wsl.exe -ArgumentList '--', 'sleep', 'infinity' -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 2

$board = Get-BoardBusId (usbipd list)
if ($null -eq $board) { Fail 'Placa ESP32 não encontrada. Plugue a placa (cabo de dados) e abra de novo.' }
if ($board.State -eq 'Not shared') {
    Fail "A placa ($($board.BusId)) ainda não foi compartilhada. Abra um PowerShell como administrador e rode:`n  usbipd bind --busid $($board.BusId)"
}
if ($board.State -eq 'Shared') { usbipd attach --wsl --busid $board.BusId | Out-Null }

# Laço de re-attach: se a placa for replugada, ela volta para o WSL sozinha.
$loop = Start-Job -ArgumentList $PSScriptRoot -ScriptBlock {
    param($dir)
    . "$dir\usb.ps1"
    while ($true) {
        $b = Get-BoardBusId (usbipd list)
        if ($b -and $b.State -eq 'Shared') { usbipd attach --wsl --busid $b.BusId | Out-Null }
        Start-Sleep -Seconds 5
    }
}

$userHome = (wsl.exe -- bash -lc 'echo $HOME').Trim()
$wslProject = (wsl.exe -- wslpath -a "$project").Trim()
$python = (wsl.exe -- bash -lc "cd '$wslProject' && python3 -c 'import tomllib,os;d={};[d.update(tomllib.load(open(f,\"rb\"))) for f in (\"config.toml\",\"config.local.toml\") if os.path.exists(f)];print(d[\"python\"].replace(\"~\",os.environ[\"HOME\"],1))'").Trim()
try {
    wsl.exe -u root -- bash -lc "cd '$wslProject' && DISTRIB_USER_HOME='$userHome' '$python' -m distrib"
} finally {
    Stop-Job $loop -ErrorAction SilentlyContinue; Remove-Job $loop -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $keep.Id -ErrorAction SilentlyContinue
}
```

`Iniciar Distribuicao.bat`:
```bat
@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\iniciar.ps1"
```

- [ ] **Step 6: Teste manual do launcher**

Com a placa plugada, dois cliques em `Iniciar Distribuicao.bat`. Expected: abre a tela de checagem com a placa ✓. Depois, com a placa **desplugada**, a mensagem "Placa ESP32 não encontrada…". Anote o resultado no commit.

- [ ] **Step 7: Commit**

```bash
git add windows "Iniciar Distribuicao.bat"
git commit -m "feat(windows): launcher com attach automático da placa e TUI como root

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Instalação no notebook

**Files:**
- Create: `windows/instalar.ps1`, `docs/instalacao.md`

**Interfaces:**
- Consumes: `requirements.txt`, `python -m distrib atualizar-catalogo`, `windows/usb.ps1`.
- Produces: um notebook pronto a partir do guia + script.

- [ ] **Step 1: `windows/instalar.ps1`**

```powershell
# Instalação do Distribuidor de Eventos num notebook (rodar como administrador, com internet).
# Pré-requisitos manuais (docs\instalacao.md): WSL com Ubuntu 24.04 instalado e o prod.keys copiado.
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\usb.ps1"
$project = Split-Path $PSScriptRoot -Parent
$POKELDN_COMMIT = '89f761e'

Write-Host '1/6 usbipd-win'
if (-not (Get-Command usbipd -ErrorAction SilentlyContinue)) {
    winget install --exact --id dorssel.usbipd-win --accept-source-agreements --accept-package-agreements
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine')
}

Write-Host '2/6 pacotes do Ubuntu'
wsl.exe -u root -- bash -lc 'apt-get update -qq && apt-get install -y -qq git python3-venv'

Write-Host '3/6 pokeldn fixado em' $POKELDN_COMMIT
wsl.exe -- bash -lc "test -d ~/pokeldn || git -c core.autocrlf=false clone https://github.com/Decryptu/pokeldn ~/pokeldn; cd ~/pokeldn && git -c core.autocrlf=false fetch -q && git checkout -q $POKELDN_COMMIT && git config core.autocrlf false"

Write-Host '4/6 venv e dependências'
$wslProject = (wsl.exe -- wslpath -a "$project").Trim()
wsl.exe -- bash -lc "test -x ~/.venvs/pokeldn/bin/python || python3 -m venv ~/.venvs/pokeldn; cd ~/pokeldn && ~/.venvs/pokeldn/bin/pip install -q -r requirements.txt && ~/.venvs/pokeldn/bin/pip install -q -r '$wslProject/requirements.txt'"
wsl.exe -- bash -lc "sudo usermod -aG dialout `$USER"

Write-Host '5/6 catálogos (Events Gallery, ~56 MB)'
wsl.exe -- bash -lc "cd '$wslProject' && ~/.venvs/pokeldn/bin/python -m distrib atualizar-catalogo"

Write-Host '6/6 placa e atalho'
$board = Get-BoardBusId (usbipd list)
if ($board -and $board.State -eq 'Not shared') { usbipd bind --busid $board.BusId }
elseif (-not $board) { Write-Host 'Placa não plugada: depois rode "usbipd bind --busid <X>" como admin.' -ForegroundColor Yellow }
$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Distribuidor de Eventos.lnk'
$shell = New-Object -ComObject WScript.Shell
$s = $shell.CreateShortcut($lnk)
$s.TargetPath = Join-Path $project 'Iniciar Distribuicao.bat'
$s.WorkingDirectory = $project
$s.Save()
Write-Host "Pronto. Atalho criado em $lnk" -ForegroundColor Green
```

- [ ] **Step 2: `docs/instalacao.md`**

Conteúdo (em português, passo a passo, como o guia da ESP32 do vault):
1. **O que precisa:** notebook com Windows 10/11, a placa ESP32 **já gravada** com o firmware do pokeldn (feito no PC de casa: `idf.py -p /dev/ttyACM0 flash` em `pokeldn/firmware/esp32`), cabo de dados, o `prod.keys` do seu console e internet (só na instalação).
2. **WSL:** PowerShell como admin → `wsl --install -d Ubuntu-24.04` → reiniciar se pedir → abrir "Ubuntu", criar usuário e senha.
3. **Copiar o pokeldn-distrib** para o notebook (ex.: `C:\pokeldn-distrib`, via `git clone` ou pendrive).
4. **prod.keys:** no Ubuntu, `mkdir -p ~/.switch && chmod 700 ~/.switch`, copiar o arquivo (ex.: `cp /mnt/d/prod.keys ~/.switch/prod.keys`) e `chmod 600 ~/.switch/prod.keys`. Nunca dentro da pasta do projeto.
5. **Plugar a placa** e rodar, como admin: `powershell -ExecutionPolicy Bypass -File C:\pokeldn-distrib\windows\instalar.ps1`.
6. **Testar em casa:** atalho "Distribuidor de Eventos" → checagem toda ✓ → distribuir um evento para o seu próprio console (roteiro em `docs/testes-reais.md`).
7. **No evento:** internet não é necessária. Plugar a placa **antes** de abrir o atalho. Problemas comuns: placa não encontrada (cabo só de energia, ou outra porta), "não foi compartilhada" (rodar o `usbipd bind` que a mensagem mostra), placa desconectada no meio (replugar; volta sozinha).

- [ ] **Step 3: Verificar o script sem executar**

Run (PowerShell): `powershell -NoProfile -Command "$null = [scriptblock]::Create((Get-Content -Raw windows\instalar.ps1)); 'sintaxe ok'"`
Expected: `sintaxe ok`

- [ ] **Step 4: Commit**

```bash
git add windows/instalar.ps1 docs/instalacao.md
git commit -m "feat(windows): instalador do notebook e guia de instalação

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Roteiro de testes reais, README e fechamento

**Files:**
- Create: `docs/testes-reais.md`, `README.md`

**Interfaces:**
- Consumes: tudo acima.

- [ ] **Step 1: `docs/testes-reais.md`**

Um checklist com data e resultado por item, na ordem da spec (seção 9.2):
1. Prova de conceito FRLG (já feita na Task 2; copiar o resultado).
2. SwSh com cartão do Events Gallery: pela TUI, "Jungle Zarude (Western Release)" → o Sword recebe (Zarude Nv60, OT do evento).
3. Regiões SwSh: um "(Japanese Release)" e um "(Western Release)" no mesmo Sword.
4. FRLG equipe cheia: equipe com 6 → a tela mostra "equipe cheia"; libera um espaço → entrega na sessão seguinte.
5. FRLG rodízio: duas entregas seguidas do "WISHMKR Jirachi (ENG)" em saves/consoles diferentes → PIDs diferentes (a tela mostra o PID na linha "Última").
6. Trocar de evento com o SwSh no ar (`T` → outro → `Enter`); no FRLG, entre dois consoles.
7. Desplugar e replugar a placa com o SwSh no ar → "placa desconectada" → volta sozinho.
8. Ensaio geral no notebook, sem internet, a partir do atalho, com os itens 2 e 4.

- [ ] **Step 2: Executar os itens 2 a 7 com o dono** e anotar o resultado de cada um no próprio `docs/testes-reais.md`. Itens que falharem viram bugs em `Known Bugs/pokeldn - bugs.md` no vault, com o log de `logs/`.

- [ ] **Step 3: `README.md`**

Curto: o que é (1 parágrafo), aviso de que depende do pokeldn e de uma ESP32, como instalar (link para `docs/instalacao.md`), como usar (atalho → jogo → digitar a busca → Enter vai para a lista → evento → Enter; Tab alterna busca/lista; teclas F, I, T, P, Q), como atualizar o catálogo (`python -m distrib atualizar-catalogo`), onde ficam os logs (`logs/`), créditos (pokeldn de Decryptu, AGPLv3; Events Gallery do Project Pokémon; kinnay/LDN).

- [ ] **Step 4: Suíte final**

Run: `~/.venvs/pokeldn/bin/python -m pytest -v`
Expected: tudo verde (55 testes)

- [ ] **Step 5: Commit**

```bash
git add docs/testes-reais.md README.md
git commit -m "docs: README e resultado dos testes reais

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
