# Distribuidor como `.exe` nativo do Windows (Flet) — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** trocar a TUI Textual no WSL por um `Distribuidor.exe` nativo do Windows, com interface Flet, que grava a placa, distribui Mystery Gift de SwSh e FRLG e se atualiza sozinho.

**Architecture:** a lógica atual (`distributor`, `catalog`, `games/*`, `download`) fica e ganha a camada Windows (porta COM, processos-filho do próprio `.exe` com `--run/--module`, parada fechando o stdin). Uma fachada `distrib/service.py` expõe estado (`Snapshot`) e ações; a interface `ui/` (Flet 1.0.2) só fala com ela. O pokeldn entra como submódulo fixo na tag `v0.5.0` e vai dentro do `.exe` (`flet pack`).

**Tech Stack:** Python 3.14 (Windows), Flet 1.0.2, esptool 5.4.0, pyserial 3.5, pytest, PyInstaller via `flet pack`, pokeldn `v0.5.0`.

**Spec:** `docs/superpowers/specs/2026-10-03-distribuidor-exe-flet-design.md`

## Global Constraints

- Plataforma: só Windows 10/11 x64. **Nada** de WSL, `wsl.exe`, usbipd, root ou `/dev/tty*` no código final.
- pokeldn: submódulo `vendor/pokeldn` na tag `v0.5.0` = commit `37410c11e4a48c63c1bdeb3b3e0c55be04e0790d`. Não editar nada dentro dele.
- Versões fixas: `flet==1.0.2`, `flet-desktop==1.0.2`, `flet-cli==1.0.2`, `esptool==5.4.0`, `pyserial==3.5`, `pycryptodome==3.23.0`, `trio==0.33.0`, `zstandard==0.25.0`.
- Dados do usuário: `%LOCALAPPDATA%\Distribuidor\` (`prod.keys`, `config.toml`, `catalog\`, `state\`, `logs\`, `sprites\`, `updates\`). Variável `DISTRIB_DATA_DIR` sobrescreve (testes).
- Código escrito do zero: **não copiar código nem assets do `gui/` do autor**. Nosso código é MIT.
- Ícones: Lucide (`lucide-static@1.50.0`, ISC). Logo: Poké Ball em SVG próprio. Destaque `#E8445A`.
- Textos da interface em português do Brasil.
- Processos-filho: `runner.command(...)` + `runner.child_env(...)` + `runner.popen_kwargs()`; parada = fechar stdin → 15 s → `terminate` → 5 s → `kill`.
- A atualização nunca reinicia o app no meio de uma distribuição.
- Mystery Gift só de SwSh e FRLG. Nada de Trade, outros jogos ou ovos.
- Trabalhar no branch `exe-flet`; `master` só recebe o merge na Task 18.
- Rodar comandos no Git Bash a partir da raiz do repositório, com `PY=.venv/Scripts/python.exe`.

## Review Focus

1. **A porta COM muda** (placa replugada em outra USB): o serviço tem de reconhecer a porta nova e refazer o HELLO; o distribuidor usa a porta nova na próxima sessão. → teste `test_board_port_change_triggers_new_hello` na Task 12.
2. **Fechar a janela no meio de uma distribuição**: o host tem de parar limpo (rede desmontada na placa), não ficar órfão. → teste `test_shutdown_stops_the_distribution` na Task 12.
3. **Busca com acento/maiúscula e Pokémon sem sprite** (sem internet ou espécie desconhecida): a grade não pode quebrar nem sumir com o grupo. → testes `test_search_groups_ignores_accents_and_case` (Task 7) e `test_offline_returns_none_and_cools_down` (Task 9).
4. **`prod.keys` errado** (binário, vazio, outro `.keys`): recusado com motivo, sem sobrescrever o bom. → teste `test_set_keys_rejects_binary_and_keeps_the_old_file` na Task 12.
5. **Atualização numa pasta sem permissão de escrita** (ex.: `Program Files`): o `.exe` atual não pode se perder e a tela mostra erro. → testes `test_apply_rolls_back_when_the_move_fails` (Task 11) e `test_apply_update_error_is_reported` (Task 12).

---

### Task 1: Branch, submódulo do pokeldn e ambiente Windows

**Files:**
- Create: `.gitmodules`, `vendor/pokeldn` (submódulo)
- Modify: `requirements.txt`, `.gitignore`

**Interfaces:**
- Produces: `.venv/` com as dependências; `vendor/pokeldn` em `v0.5.0`.

- [ ] **Step 1: Branch e submódulo**

```bash
git checkout -b exe-flet
git submodule add https://github.com/Decryptu/pokeldn vendor/pokeldn
git -C vendor/pokeldn checkout v0.5.0
test "$(git -C vendor/pokeldn rev-parse HEAD)" = "37410c11e4a48c63c1bdeb3b3e0c55be04e0790d" && echo OK
```
Expected: `OK`.

- [ ] **Step 2: `requirements.txt` (substituir o arquivo todo)**

```text
# Executar (Windows)
flet==1.0.2
flet-desktop==1.0.2
esptool==5.4.0
pyserial==3.5
pycryptodome==3.23.0
trio==0.33.0
zstandard==0.25.0
-e ./vendor/pokeldn/vendor/LDN
# Desenvolvimento e empacotamento
pytest>=8,<9
flet-cli==1.0.2
pillow==12.3.0
# A TUI antiga sai na Task 6
textual==8.2.8
```

- [ ] **Step 3: `.gitignore` (acrescentar ao fim)**

```text
.venv/
dist/
build/out/
firmware/
*.spec
```

- [ ] **Step 4: venv e instalação**

```bash
py -3.14 -m venv .venv
PY=.venv/Scripts/python.exe
$PY -m pip install -q --upgrade pip
$PY -m pip install -q -r requirements.txt
$PY -c "import sys; sys.path[:0]=['vendor/pokeldn','vendor/pokeldn/vendor/LDN']; import flet, esptool, serial; from pokeldn.ldn import esp32; from pokeldn.swsh import wc8; from pokeldn.frlg.save.species_names import SPECIES; print('ok', flet.__version__ if hasattr(flet,'__version__') else '')"
```
Expected: linha começando com `ok`. Se `pip` não resolver `flet-cli==1.0.2` com `pillow==12.3.0`, remova o pin do pillow (deixe `pillow`) e anote no commit.

- [ ] **Step 5: Commit**

```bash
git add .gitmodules vendor/pokeldn requirements.txt .gitignore
git commit -m "Submódulo pokeldn v0.5.0 e dependências do Windows"
```

---

### Task 2: Prova na placa real (manual: Opus + dono, com a placa e um Switch)

Não é tarefa de subagente. Prova que os hosts do v0.5.0 rodam no Windows nativo e grava os logs reais que as Tasks 8 e 12 usam.

**Files:**
- Create: `tests/fixtures/logs/swsh_v050.txt`, `tests/fixtures/logs/frlg_v050.txt`

- [ ] **Step 1: Soltar a placa do WSL** (PowerShell como administrador; o dono executa)

```powershell
usbipd list
usbipd detach --busid 1-6
usbipd unbind --busid 1-6
```
Depois: `.venv/Scripts/python.exe -m serial.tools.list_ports -v` deve mostrar uma `COMx` com `VID:PID=1A86:55D4` (CH9102). Sem porta: instalar o driver CH343/CH9102 da WCH (`https://www.wch-ic.com/downloads/CH343SER_EXE.html`). Anote a porta (ex.: `COM5`) e use-a nos passos seguintes, **substituindo `COM5` pelo valor real** antes de entregar os comandos ao dono.

- [ ] **Step 2: `prod.keys` na pasta de dados**

```bash
mkdir -p "$LOCALAPPDATA/Distribuidor"
wsl -e sh -c 'cat ~/.switch/prod.keys' > "$LOCALAPPDATA/Distribuidor/prod.keys"
wc -l "$LOCALAPPDATA/Distribuidor/prod.keys"
```
Expected: dezenas de linhas. (Este é o único uso do WSL no projeto, só para pegar o arquivo do dono.)

- [ ] **Step 3: SwSh nativo** (o dono roda num PowerShell na raiz do repositório, com o Sword pronto em Presente Misterioso → Receber presente → Por comunicação local)

```powershell
$env:POKELDN_RADIO = "esp32:COM5"
cd vendor\pokeldn
..\..\.venv\Scripts\python.exe -u bin\swsh_gift_host.py --record "..\..\tests\fixtures\gallery\Released\Gen 8\SwSh\Wondercards\0507 SWSH - Jungle Zarude (Western Release).wc8" --keys "$env:LOCALAPPDATA\Distribuidor\prod.keys" --seconds 600 --no-validate 2>&1 | Tee-Object ..\..\tests\fixtures\logs\swsh_v050.txt
```
Confirme no console que o cartão aparece e pode ser recebido; depois Ctrl+C. Aceite: o log tem `[host] AP up: ... ch=N`, `advertising comm id ...`, e termina com `stopping` / `served N advertisements` (parada limpa). Se o nome do arquivo `.wc8` for outro, use `ls tests/fixtures/gallery/Released/Gen\ 8/SwSh/Wondercards/`.

- [ ] **Step 4: FRLG nativo** (FireRed em MYSTERY GIFT → WONDER CARDS → FRIEND)

```powershell
$env:POKELDN_RADIO = "esp32:COM5"
cd vendor\pokeldn
..\..\.venv\Scripts\python.exe -u bin\frlg_mg_host.py --live --gift master-ball --end-on-success --keys "$env:LOCALAPPDATA\Distribuidor\prod.keys" --phy auto --idle-timeout 300 2>&1 | Tee-Object ..\..\tests\fixtures\logs\frlg_v050.txt
```
Aceite: o host termina sozinho após a entrega; o log tem `Hosting. Waiting for the console to join (... channel N).`, `A console joined the network.` e `Mystery Event script status: 2` ou `... delivered. On the Switch`.

- [ ] **Step 5: Conferir as linhas que o código atual reconhece**

```bash
grep -n -E "AP up: .* ch=|advertising comm id|Traceback" tests/fixtures/logs/swsh_v050.txt | head
grep -n -E "Hosting\. Waiting|A console joined|script status|delivered\. On the Switch|without delivering|Traceback" tests/fixtures/logs/frlg_v050.txt | head
```
Se alguma linha esperada não existir ou vier com outro texto, **pare** e corrija os padrões da Task 8 (`_CHANNEL`, `_HOSTING`, `_STATUS`, `_CONSOLE`) com o texto real antes de despachá-la. Se algum host falhar no Windows, pare o plano e investigue (superpowers:systematic-debugging): é o risco 1 da spec.

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/logs
git commit -m "Logs reais dos hosts do pokeldn v0.5.0 no Windows nativo"
```

---

### Task 3: Configuração do Windows

**Files:**
- Modify: `distrib/config.py` (reescrever), `tests/conftest.py`, `tests/test_config.py` (reescrever)
- Delete: `config.toml`

**Interfaces:**
- Produces:
  - `config.APP_NAME = "Distribuidor"`, `config.PROJECT_DIR: Path`
  - `config.resource_root() -> Path` (`sys._MEIPASS` no `.exe`, senão a raiz do repo)
  - `config.default_data_dir() -> Path`
  - `Config(data_dir, pokeldn_dir, firmware_dir, keys, catalog_dir, state_dir, logs_dir, sprites_dir, frlg_idle_timeout)` (frozen dataclass)
  - `config.load(data_dir: Path | None = None, root: Path | None = None) -> Config`

- [ ] **Step 1: Testes que falham — `tests/test_config.py` (substituir)**

```python
import sys
from pathlib import Path

from distrib import config as configmod


def test_paths_live_in_the_data_dir(tmp_path):
    cfg = configmod.load(data_dir=tmp_path, root=tmp_path / "root")
    assert cfg.data_dir == tmp_path
    assert cfg.keys == tmp_path / "prod.keys"
    assert cfg.catalog_dir == tmp_path / "catalog"
    assert cfg.state_dir == tmp_path / "state"
    assert cfg.logs_dir == tmp_path / "logs"
    assert cfg.sprites_dir == tmp_path / "sprites"
    assert cfg.pokeldn_dir == tmp_path / "root" / "vendor" / "pokeldn"
    assert cfg.firmware_dir == tmp_path / "root" / "firmware"
    assert cfg.frlg_idle_timeout == 120


def test_settings_file_overrides(tmp_path):
    (tmp_path / "config.toml").write_text("frlg_idle_timeout = 30\n", encoding="utf-8")
    assert configmod.load(data_dir=tmp_path).frlg_idle_timeout == 30


def test_default_data_dir_uses_localappdata(monkeypatch, tmp_path):
    monkeypatch.delenv("DISTRIB_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert configmod.default_data_dir() == tmp_path / "Distribuidor"


def test_env_overrides_the_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("DISTRIB_DATA_DIR", str(tmp_path / "x"))
    assert configmod.default_data_dir() == tmp_path / "x"


def test_frozen_root_is_meipass(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert configmod.resource_root() == tmp_path


def test_real_pokeldn_checkout():
    cfg = configmod.load()
    assert (cfg.pokeldn_dir / "bin" / "swsh_gift_host.py").exists()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `$PY -m pytest tests/test_config.py -q`
Expected: FAIL (`load()` não aceita `data_dir`).

- [ ] **Step 3: `distrib/config.py` (substituir)**

```python
"""Configuração e caminhos do Windows: os dados do usuário ficam em %LOCALAPPDATA%\\Distribuidor."""
from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "Distribuidor"
PROJECT_DIR = Path(__file__).resolve().parent.parent


def resource_root() -> Path:
    """Onde estão o pokeldn, os firmwares e os assets: a pasta do .exe extraído, ou o repositório."""
    return Path(getattr(sys, "_MEIPASS", PROJECT_DIR))


def default_data_dir() -> Path:
    if override := os.environ.get("DISTRIB_DATA_DIR"):
        return Path(override)
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / APP_NAME if base else Path.home() / f".{APP_NAME.lower()}"


@dataclass(frozen=True)
class Config:
    data_dir: Path
    pokeldn_dir: Path
    firmware_dir: Path
    keys: Path
    catalog_dir: Path
    state_dir: Path
    logs_dir: Path
    sprites_dir: Path
    frlg_idle_timeout: int


def load(data_dir: Path | None = None, root: Path | None = None) -> Config:
    data_dir = data_dir or default_data_dir()
    root = root or resource_root()
    settings: dict = {}
    file = data_dir / "config.toml"
    if file.exists():
        settings = tomllib.loads(file.read_text(encoding="utf-8"))
    return Config(
        data_dir=data_dir,
        pokeldn_dir=root / "vendor" / "pokeldn",
        firmware_dir=root / "firmware",
        keys=data_dir / "prod.keys",
        catalog_dir=data_dir / "catalog",
        state_dir=data_dir / "state",
        logs_dir=data_dir / "logs",
        sprites_dir=data_dir / "sprites",
        frlg_idle_timeout=int(settings.get("frlg_idle_timeout", 120)),
    )
```

- [ ] **Step 4: `tests/conftest.py` (substituir)**

```python
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
```

- [ ] **Step 5: Apagar o `config.toml` versionado e rodar**

```bash
git rm -q config.toml
$PY -m pytest tests/test_config.py tests/test_catalog.py tests/test_download.py tests/test_frlg_gift.py -q
$PY -m pytest -q 2>&1 | tail -15
```
Expected: os quatro primeiros arquivos passam. Na suíte toda, só podem falhar testes de `test_radio.py`, `test_distributor.py`, `test_main.py`, `test_app.py`, `test_config_valor.py`, `test_swsh.py::test_build_job` e `test_frlg.py::test_build_job_for_pk3_and_extra` (consertados nas Tasks 5, 6, 8 e 17). Liste as falhas reais no corpo do commit.

- [ ] **Step 6: Commit**

```bash
git add distrib/config.py tests/conftest.py tests/test_config.py
git commit -m "Config do Windows: dados em %LOCALAPPDATA%\\Distribuidor, pokeldn do submódulo"
```

---

### Task 4: Processos-filho do próprio app (`runner.py` + `main.py`)

**Files:**
- Create: `distrib/runner.py`, `main.py`, `tests/child_script.py`, `tests/test_runner.py`

**Interfaces:**
- Consumes: `config.PROJECT_DIR`, `config.load().pokeldn_dir`, `pokeldn_path.ensure_importable`.
- Produces:
  - `runner.MANAGED = "DISTRIB_MANAGED_RUN"`
  - `runner.command(*argv: str) -> list[str]`
  - `runner.child_env(extra: dict[str, str] | None = None, managed: bool = True) -> dict[str, str]`
  - `runner.popen_kwargs() -> dict` (stdin/stdout em PIPE, stderr→stdout, utf-8, sem janela)
  - `runner.is_child(argv: list[str]) -> bool`
  - `runner.child(argv: list[str], pokeldn_dir: Path) -> None`
  - `main.py`: `python main.py --run <script do pokeldn> [args]` / `--module <módulo> [args]`; sem esses argumentos abre a interface (`ui.app.run`, Task 13).

- [ ] **Step 1: `tests/child_script.py`**

```python
"""Usado pelos testes do runner: imprime os argumentos; 'wait' espera até ser interrompido."""
import sys
import time

code, *words = sys.argv[1:]
print("args", *words, flush=True)
try:
    if code == "wait":
        time.sleep(30)
except KeyboardInterrupt:
    print("interrompido", flush=True)
    sys.exit(130)
sys.exit(0 if code == "wait" else int(code))
```

- [ ] **Step 2: Testes que falham — `tests/test_runner.py`**

```python
import subprocess
import sys

from distrib import runner
from distrib.config import PROJECT_DIR


def test_command_in_source_mode():
    assert runner.command("--run", "bin/x.py", "-v") == [
        sys.executable, "-u", str(PROJECT_DIR / "main.py"), "--run", "bin/x.py", "-v"]


def test_command_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert runner.command("--module", "m") == [sys.executable, "--module", "m"]


def test_is_child():
    assert runner.is_child(["--run", "bin/x.py"])
    assert runner.is_child(["--module", "a.b", "x"])
    assert not runner.is_child([])
    assert not runner.is_child(["--run"])
    assert not runner.is_child(["outro", "x"])


def test_child_env_managed_flag():
    assert runner.child_env({"A": "1"})[runner.MANAGED] == "1"
    assert runner.child_env({"A": "1"})["A"] == "1"
    assert runner.MANAGED not in runner.child_env(managed=False)


def _spawn(*argv, managed=True):
    return subprocess.Popen(runner.command(*argv), cwd=str(PROJECT_DIR),
                            env=runner.child_env(managed=managed), **runner.popen_kwargs())


def test_module_child_runs_and_exits_with_its_code():
    proc = _spawn("--module", "tests.child_script", "3", "ola", managed=False)
    out, _ = proc.communicate(timeout=60)
    assert "args ola" in out
    assert proc.returncode == 3


def test_closing_stdin_interrupts_a_managed_child():
    proc = _spawn("--module", "tests.child_script", "wait")
    assert proc.stdout.readline().strip() == "args"
    proc.stdin.close()
    assert proc.wait(timeout=20) == 130
    assert "interrompido" in proc.stdout.read()


def test_run_mode_runs_a_pokeldn_script():
    proc = _spawn("--run", "bin/swsh_gift_host.py", "--help", managed=False)
    out, _ = proc.communicate(timeout=120)
    assert proc.returncode == 0, out
    assert "--record" in out
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `$PY -m pytest tests/test_runner.py -q`
Expected: FAIL (`No module named 'distrib.runner'`).

- [ ] **Step 4: `distrib/runner.py`**

```python
"""Processos-filho do próprio app.

O .exe (ou o Python, no desenvolvimento) se chama de novo com `--run <script do pokeldn>` ou
`--module <módulo>`. Um processo sem janela no Windows não recebe Ctrl+C: o pai fecha o stdin e,
com DISTRIB_MANAGED_RUN=1, o filho transforma esse fim de arquivo em KeyboardInterrupt, que é
como os hosts do pokeldn desmontam a rede na placa.
"""
from __future__ import annotations

import _thread
import os
import runpy
import subprocess
import sys
import threading
from pathlib import Path

from distrib.config import PROJECT_DIR
from distrib.pokeldn_path import ensure_importable

MANAGED = "DISTRIB_MANAGED_RUN"
MODES = ("--run", "--module")


def command(*argv: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, *argv]
    return [sys.executable, "-u", str(PROJECT_DIR / "main.py"), *argv]


def child_env(extra: dict[str, str] | None = None, managed: bool = True) -> dict[str, str]:
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8", **(extra or {})}
    if managed:
        env[MANAGED] = "1"
    else:
        env.pop(MANAGED, None)
    return env


def popen_kwargs() -> dict:
    return dict(stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)


def is_child(argv: list[str]) -> bool:
    return len(argv) >= 2 and argv[0] in MODES


def _interrupt_on_stdin_close() -> None:
    try:
        sys.stdin.read()
    except (OSError, ValueError):
        pass
    _thread.interrupt_main()


def child(argv: list[str], pokeldn_dir: Path) -> None:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:
            stream.reconfigure(encoding="utf-8", line_buffering=True)
    if sys.stdin is not None and os.environ.get(MANAGED):
        threading.Thread(target=_interrupt_on_stdin_close, daemon=True).start()
    ensure_importable(pokeldn_dir)
    mode, target, *args = argv
    if mode == "--run":
        path = pokeldn_dir / target
        sys.argv = [str(path), *args]
        sys.path.insert(0, str(path.parent))
        runpy.run_path(str(path), run_name="__main__")
    else:
        sys.argv = [target, *args]
        runpy.run_module(target, run_name="__main__", alter_sys=True)
```

- [ ] **Step 5: `main.py` (raiz do repositório)**

```python
"""Ponto de entrada do Distribuidor: `python main.py` no desenvolvimento, ou o próprio .exe."""
import sys


def main() -> None:
    argv = sys.argv[1:]
    from distrib import runner
    if runner.is_child(argv):
        from distrib.config import load
        runner.child(argv, load().pokeldn_dir)
        return
    from ui.app import run
    run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Rodar**

Run: `$PY -m pytest tests/test_runner.py -q`
Expected: 7 passed.

- [ ] **Step 7: Commit**

```bash
git add distrib/runner.py main.py tests/child_script.py tests/test_runner.py
git commit -m "Runner: o app se reinvoca com --run/--module e para fechando o stdin"
```

---

### Task 5: Distributor no Windows (parada pelo stdin, log ao vivo)

**Files:**
- Modify: `distrib/distributor.py`, `tests/fake_host.py`, `tests/test_distributor.py`

**Interfaces:**
- Consumes: `runner.child_env`, `runner.popen_kwargs`.
- Produces: `Distributor(mode, parse_line, job_factory, log_path, find_port, max_failures=3, retry_delay=3.0, watch_interval=1.0, clock=time.monotonic, on_line: Callable[[str], None] | None = None, stop_grace: float = 15.0)`. `on_line` recebe cada linha já com hora (`"21:04:05 texto"`). O resto da API (`start/stop/pause/resume/status/running`, `Status`) não muda.

- [ ] **Step 1: `tests/fake_host.py` (substituir)**

```python
"""Imita um host: imprime o roteiro passado em argv e sai com o código dado.

    python tests/fake_host.py EXIT_CODE 'linha 1' 'sleep:0.2' 'linha 2' ...

Com DISTRIB_MANAGED_RUN=1, fechar o stdin vira KeyboardInterrupt (como no runner): imprime
"interrompido" e sai com 130. O item "deaf" desliga isso, para testar o terminate.
"""
import _thread
import os
import sys
import threading
import time

code, *script = sys.argv[1:]
deaf = "deaf" in script
script = [item for item in script if item != "deaf"]


def _watch_stdin():
    sys.stdin.read()
    _thread.interrupt_main()


if os.environ.get("DISTRIB_MANAGED_RUN") and sys.stdin is not None and not deaf:
    threading.Thread(target=_watch_stdin, daemon=True).start()
try:
    for item in script:
        if item.startswith("sleep:"):
            time.sleep(float(item[6:]))
        else:
            print(item, flush=True)
except KeyboardInterrupt:
    print("interrompido", flush=True)
    sys.exit(130)
sys.exit(int(code))
```

- [ ] **Step 2: Ajustar `tests/test_distributor.py`**

Troque toda ocorrência de `"/dev/ttyACM0"` por `"COM5"`. Troque a função `make` por esta (aceita `on_line` e `stop_grace`):

```python
def make(tmp_path, mode, factory, find=lambda: "COM5", **kw):
    parse = SwshAdapter().parse_line if mode == "broadcast" else FrlgAdapter(None).parse_line
    return Distributor(mode, parse, factory, tmp_path / "log.txt", find,
                       retry_delay=0.05, watch_interval=0.05, **kw)
```

Acrescente ao fim do arquivo:

```python
def test_on_line_gets_each_log_line_with_time(tmp_path):
    seen = []
    d = make(tmp_path, "broadcast", job(0, "advertising comm id 0x1", "sleep:5"), on_line=seen.append)
    d.start()
    assert wait_for(lambda: any("advertising comm id" in line for line in seen))
    d.stop()
    line = next(line for line in seen if "advertising" in line)
    assert line[2] == ":" and line[5] == ":"        # "HH:MM:SS texto"


def test_stop_terminates_a_host_that_ignores_stdin(tmp_path):
    d = make(tmp_path, "broadcast", job(0, "deaf", "advertising comm id 0x1", "sleep:30"),
             stop_grace=0.3)
    d.start()
    assert wait_for(lambda: d.status().state == "on_air")
    started = time.monotonic()
    d.stop()
    assert time.monotonic() - started < 8
    assert d.status().state == "idle"
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `$PY -m pytest tests/test_distributor.py -q`
Expected: FAIL (`on_line`/`stop_grace` desconhecidos; e no Windows o `SIGINT` atual levanta `ValueError`).

- [ ] **Step 4: Mudanças em `distrib/distributor.py`**

1. Imports: remova `import signal`; acrescente `from distrib import runner`.
2. Assinatura e atributos do `__init__`:

```python
    def __init__(self, mode: str, parse_line: Callable[[str], Update | None],
                 job_factory: Callable[[str], Job], log_path: Path,
                 find_port: Callable[[], str | None], max_failures: int = 3,
                 retry_delay: float = 3.0, watch_interval: float = 1.0, clock=time.monotonic,
                 on_line: Callable[[str], None] | None = None, stop_grace: float = 15.0):
        self.mode, self.parse_line, self.job_factory = mode, parse_line, job_factory
        self.log_path, self.find_port = log_path, find_port
        self.max_failures, self.retry_delay, self.clock = max_failures, retry_delay, clock
        self.watch_interval, self.on_line, self.stop_grace = watch_interval, on_line, stop_grace
```
(o resto do `__init__` continua igual).

3. `_log` passa a avisar `on_line`:

```python
    def _log(self, line: str) -> None:
        stamped = f"{datetime.now():%H:%M:%S} {line}"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(stamped + "\n")
        if self.on_line is not None:
            self.on_line(stamped)
```

4. `_kill` (substituir):

```python
    def _kill(self) -> None:
        # Fechar o stdin vira KeyboardInterrupt no filho (distrib.runner): é assim que os hosts do
        # pokeldn desmontam a rede na placa. Um processo sem janela no Windows não recebe Ctrl+C.
        with self._proc_lock:
            proc = self._proc
            if proc is None or proc.poll() is not None:
                return

            def close_stdin():
                try:
                    if proc.stdin is not None:
                        proc.stdin.close()
                except OSError:
                    pass

            for send, wait in ((close_stdin, self.stop_grace), (proc.terminate, 5), (proc.kill, None)):
                send()
                try:
                    proc.wait(timeout=wait)
                    return
                except subprocess.TimeoutExpired:
                    continue
```

5. Em `_spawn`, troque o `Popen` por:

```python
            self._proc = subprocess.Popen(job.argv, cwd=job.cwd, env=runner.child_env(job.env),
                                          **runner.popen_kwargs())
```
e apague a linha `env = {**os.environ, **job.env}`; remova `import os` se não sobrar uso.

- [ ] **Step 5: Rodar**

Run: `$PY -m pytest tests/test_distributor.py -q`
Expected: todos passam (incluindo o teste antigo que procura `"interrompido"` no log).

- [ ] **Step 6: Commit**

```bash
git add distrib/distributor.py tests/fake_host.py tests/test_distributor.py
git commit -m "Distributor no Windows: parada fechando o stdin, on_line para o log ao vivo"
```

---

### Task 6: Placa por porta COM, HELLO pelo runner; sai a TUI

**Files:**
- Modify: `distrib/radio.py` (reescrever), `tests/test_radio.py` (reescrever), `distrib/__main__.py`, `tests/test_main.py`, `requirements.txt`
- Create: `distrib/runners/hello.py`
- Delete: `distrib/app.py`, `tests/test_app.py`

**Interfaces:**
- Consumes: `runner.command`, `runner.child_env`.
- Produces:
  - `radio.BRIDGES: dict[tuple[int, int], str]`, `radio.DRIVERS: dict[str, str]`
  - `radio.Port(device: str, bridge: str)` (frozen dataclass)
  - `radio.list_boards(comports=list_ports.comports) -> list[Port]` (ordenada por `device`, só portas com VID)
  - `radio.find_port(comports=list_ports.comports) -> str | None` (a porta, se houver exatamente uma)
  - `radio.hello(port: str, cfg: Config, run=subprocess.run) -> str` (texto do firmware) e `radio.RadioError`
  - `python main.py --module distrib.runners.hello COM5` imprime o texto do HELLO.

- [ ] **Step 1: Testes que falham — `tests/test_radio.py` (substituir)**

```python
import subprocess
from types import SimpleNamespace as NS

import pytest

from distrib import radio, runner


def ports(*items):
    return lambda: [NS(device=d, vid=v, pid=p) for d, v, p in items]


def test_list_boards_names_bridges_and_skips_virtual_ports():
    boards = radio.list_boards(ports(("COM7", 0x10C4, 0xEA60), ("COM1", None, None),
                                     ("COM5", 0x1A86, 0x55D4), ("COM9", 0x1234, 0x5678)))
    assert boards == [radio.Port("COM5", "CH9102"), radio.Port("COM7", "CP210x"),
                      radio.Port("COM9", "desconhecida")]


def test_find_port_single_and_ambiguous():
    assert radio.find_port(ports(("COM5", 0x1A86, 0x55D4), ("COM1", None, None))) == "COM5"
    assert radio.find_port(ports()) is None
    assert radio.find_port(ports(("COM5", 0x1A86, 0x55D4), ("COM7", 0x10C4, 0xEA60))) is None


def test_every_known_bridge_with_a_driver_has_a_link():
    for bridge in ("CP210x", "CH340", "CH9102"):
        assert radio.DRIVERS[bridge].startswith("https://")


def test_hello_ok_and_error(cfg):
    seen = {}

    def ok(argv, **kw):
        seen["argv"], seen["kw"] = argv, kw
        return subprocess.CompletedProcess(argv, 0, "x\nESP32 pokeldn radio v7\n", "")

    assert radio.hello("COM5", cfg, run=ok) == "ESP32 pokeldn radio v7"
    assert seen["argv"] == runner.command("--module", "distrib.runners.hello", "COM5")
    assert runner.MANAGED not in seen["kw"]["env"]

    def bad(argv, **kw):
        return subprocess.CompletedProcess(argv, 1, "", "Traceback\nPermissionError: Access is denied")

    with pytest.raises(radio.RadioError, match="Access is denied"):
        radio.hello("COM5", cfg, run=bad)


def test_hello_timeout(cfg):
    def slow(argv, **kw):
        raise subprocess.TimeoutExpired(argv, 20)

    with pytest.raises(radio.RadioError, match="não respondeu"):
        radio.hello("COM5", cfg, run=slow)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `$PY -m pytest tests/test_radio.py -q`
Expected: FAIL (`list_boards` não existe).

- [ ] **Step 3: `distrib/radio.py` (substituir)**

```python
"""A placa: achar a porta COM e fazer o HELLO (num processo-filho, como os hosts)."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from serial.tools import list_ports

from distrib import runner
from distrib.config import Config

BRIDGES = {
    (0x10C4, 0xEA60): "CP210x",
    (0x1A86, 0x7523): "CH340",
    (0x1A86, 0x55D4): "CH9102",
    (0x0403, 0x6001): "FT232R",
    (0x303A, 0x1001): "USB nativo do ESP32",
}
DRIVERS = {
    "CP210x": "https://www.silabs.com/developer-tools/usb-to-uart-bridge-vcp-drivers",
    "CH340": "https://www.wch-ic.com/downloads/CH341SER_EXE.html",
    "CH9102": "https://www.wch-ic.com/downloads/CH343SER_EXE.html",
}


class RadioError(Exception):
    pass


@dataclass(frozen=True)
class Port:
    device: str
    bridge: str


def list_boards(comports=list_ports.comports) -> list[Port]:
    found = [Port(p.device, BRIDGES.get((p.vid, p.pid), "desconhecida"))
             for p in comports() if p.vid is not None]
    return sorted(found, key=lambda p: p.device)


def find_port(comports=list_ports.comports) -> str | None:
    boards = list_boards(comports)
    return boards[0].device if len(boards) == 1 else None


def hello(port: str, cfg: Config, run=subprocess.run) -> str:
    try:
        done = run(runner.command("--module", "distrib.runners.hello", port),
                   cwd=str(cfg.pokeldn_dir), env=runner.child_env(managed=False),
                   stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=20,
                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except subprocess.TimeoutExpired as exc:
        raise RadioError(f"a placa em {port} não respondeu em 20 s") from exc
    if done.returncode != 0:
        lines = done.stderr.strip().splitlines() or done.stdout.strip().splitlines()
        raise RadioError(f"HELLO falhou em {port}: {(lines or ['erro desconhecido'])[-1]}")
    return done.stdout.strip().splitlines()[-1]
```

- [ ] **Step 4: `distrib/runners/hello.py`**

```python
"""HELLO na placa: python main.py --module distrib.runners.hello COM5"""
import sys

from pokeldn.ldn import esp32


def main(argv=None) -> int:
    port = (argv if argv is not None else sys.argv[1:])[0]
    radio = esp32.Radio.open_serial(port)
    try:
        print(radio.hello().text, flush=True)
    finally:
        radio.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Tirar a TUI**

```bash
git rm -q distrib/app.py tests/test_app.py
```
`requirements.txt`: apague as linhas `# A TUI antiga sai na Task 6` e `textual==8.2.8`.

`distrib/__main__.py` (substituir):

```python
"""python -m distrib atualizar-catalogo [swsh|frlg]  (atalho de desenvolvimento)"""
from __future__ import annotations

import argparse
import sys

from distrib import config as configmod
from distrib.pokeldn_path import ensure_importable


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m distrib")
    sub = parser.add_subparsers(dest="cmd", required=True)
    up = sub.add_parser("atualizar-catalogo", help="baixa o Events Gallery e remonta os catálogos")
    up.add_argument("jogos", nargs="*", choices=("swsh", "frlg"))
    args = parser.parse_args(argv)
    cfg = configmod.load()
    ensure_importable(cfg.pokeldn_dir)
    from distrib import download
    download.update_catalogs(cfg, tuple(args.jogos or ("swsh", "frlg")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`tests/test_main.py`: apague `test_checar_prints_and_returns_code` (mantenha `test_atualizar_catalogo_calls_download`).

- [ ] **Step 6: Rodar**

```bash
$PY -m pytest tests/test_radio.py tests/test_main.py -q
grep -rn "textual\|run_checks\|/dev/tty" distrib tests | grep -v fixtures
```
Expected: testes passam; o grep não acha nada.

- [ ] **Step 7: Commit**

```bash
git add -A distrib tests requirements.txt
git commit -m "Placa por porta COM e HELLO pelo runner; sai a TUI Textual"
```

---

### Task 7: Espécies e agrupamento por Pokémon no catálogo

**Files:**
- Create: `build/gen_species.py`, `distrib/species_data.py` (gerado), `distrib/species.py`, `tests/test_species.py`
- Modify: `distrib/catalog.py`, `tests/test_catalog.py`

**Interfaces:**
- Produces:
  - `species.name(national: int) -> str` (nome em inglês, ou `"#N"`)
  - `species.gen3_to_national(internal: int) -> int` (0 se não for espécie)
  - `Event` ganha `species: int = 0`, `highlights: tuple[str, ...] = ()`, `region: str = ""`; `INDEX_VERSION = 2`
  - `catalog.Group(key: str, name: str, species: int, events: tuple[Event, ...], highlights: tuple[str, ...])`
  - `catalog.group_events(events: list[Event], species_name: Callable[[int], str]) -> list[Group]`
  - `catalog.search_groups(groups: list[Group], text: str) -> list[Group]`

- [ ] **Step 1: `build/gen_species.py`**

```python
"""Gera distrib/species_data.py a partir dos CSVs do PokeAPI. Rodar só quando faltar espécie."""
import csv
import io
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/"
OUT = Path(__file__).resolve().parent.parent / "distrib" / "species_data.py"


def fetch(name: str) -> list[dict]:
    with urllib.request.urlopen(BASE + name, timeout=60) as resp:
        return list(csv.DictReader(io.TextIOWrapper(resp, encoding="utf-8")))


def main() -> None:
    english = {int(r["pokemon_species_id"]): r["name"]
               for r in fetch("pokemon_species_names.csv") if r["local_language_id"] == "9"}
    rows = sorted((int(r["id"]), r["identifier"], english[int(r["id"])])
                  for r in fetch("pokemon_species.csv"))
    lines = ['"""Gerado por build/gen_species.py a partir do PokeAPI. Não editar à mão."""', "",
             "# número nacional: (identificador do PokeAPI, nome em inglês)", "SPECIES = {"]
    lines += [f"    {n}: ({ident!r}, {name!r})," for n, ident, name in rows]
    lines += ["}", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(rows)} espécies em {OUT}")


if __name__ == "__main__":
    main()
```

Run: `$PY build/gen_species.py`
Expected: `1025 espécies em ...` (ou mais, se o PokeAPI tiver crescido).

- [ ] **Step 2: Testes que falham — `tests/test_species.py`**

```python
from pokeldn.frlg.save.species_names import SPECIES as GEN3

from distrib import species

INTERNAL = {name: n for n, name in GEN3.items()}


def test_name():
    assert species.name(25) == "Pikachu"
    assert species.name(893) == "Zarude"
    assert species.name(99999) == "#99999"


def test_gen3_to_national_known_cases():
    assert species.gen3_to_national(25) == 25
    assert species.gen3_to_national(INTERNAL["TREECKO"]) == 252
    assert species.gen3_to_national(INTERNAL["CHIMECHO"]) == 358
    assert species.gen3_to_national(INTERNAL["NIDORAN_F"]) == 29
    assert species.gen3_to_national(INTERNAL["MR_MIME"]) == 122
    assert species.gen3_to_national(INTERNAL["HO_OH"]) == 250
    assert species.gen3_to_national(INTERNAL["DEOXYS"]) == 386
    assert species.gen3_to_national(0) == 0


def test_gen3_covers_the_whole_hoenn_dex():
    found = {species.gen3_to_national(n) for n, name in GEN3.items()
             if name != "NONE" and not name.startswith("OLD_")}
    assert set(range(1, 387)) <= found
```

- [ ] **Step 3: `distrib/species.py`**

```python
"""Nomes das espécies e a conversão do índice interno da Gen 3 para o número nacional."""
from __future__ import annotations

from functools import lru_cache

from distrib.species_data import SPECIES


def name(national: int) -> str:
    entry = SPECIES.get(national)
    return entry[1] if entry else f"#{national}"


@lru_cache(maxsize=1)
def _by_identifier() -> dict[str, int]:
    return {ident: n for n, (ident, _) in SPECIES.items()}


def gen3_to_national(internal: int) -> int:
    """0 quando o índice não é de uma espécie (vazio, ou os Unown 'OLD_' do cartucho)."""
    from pokeldn.frlg.save.species_names import SPECIES as GEN3
    gen3 = GEN3.get(internal, "")
    if not gen3 or gen3 == "NONE" or gen3.startswith("OLD_"):
        return 0
    return _by_identifier().get(gen3.lower().replace("_", "-"), 0)
```

Run: `$PY -m pytest tests/test_species.py -q` → passa. Se algum nome da Gen 3 não bater com o identificador do PokeAPI, acrescente um dicionário `_GEN3_FIX = {"NOME_GEN3": "identificador-pokeapi"}` consultado antes do `.lower().replace(...)` e um teste para ele.

- [ ] **Step 4: Testes que falham — acrescentar a `tests/test_catalog.py`**

```python
from distrib.catalog import Event, group_events, search_groups


def ev(key, species=0, kind="pokemon", name=None, highlights=(), region=""):
    return Event(game="swsh", key=key, name=name or key, kind=kind, details=(), files=(key,),
                 sort_key=key, species=species, highlights=highlights, region=region)


NAMES = {893: "Zarude", 25: "Pikachu"}.get


def test_group_events_by_species_items_last():
    groups = group_events([ev("b", 893, highlights=("Nv 60",)), ev("a", 25, highlights=("Shiny",)),
                           ev("c", 893, highlights=("Nv 70", "Nv 60")), ev("i", kind="item"),
                           ev("x", kind="extra")], lambda n: NAMES(n, f"#{n}"))
    assert [g.name for g in groups] == ["Pikachu", "Zarude", "Itens", "Presentes do pokeldn"]
    zarude = groups[1]
    assert zarude.key == "pokemon:893" and zarude.species == 893
    assert [e.key for e in zarude.events] == ["b", "c"]
    assert zarude.highlights == ("Nv 60", "Nv 70")


def test_search_groups_ignores_accents_and_case():
    groups = group_events([ev("Jungle Zarude", 893), ev("Pikachu Chapéu", 25)],
                          lambda n: NAMES(n, f"#{n}"))
    assert [g.name for g in search_groups(groups, "ZARUDE")] == ["Zarude"]
    assert [g.name for g in search_groups(groups, "chapeu")] == ["Pikachu"]
    assert search_groups(groups, "") == groups


def test_index_roundtrip_keeps_new_fields(tmp_path):
    from distrib.catalog import Catalog, load_index, save_index
    cat = Catalog("swsh", [ev("z", 893, highlights=("Shiny",), region="Ocidente")])
    save_index(cat, tmp_path / "index.json")
    back = load_index("swsh", tmp_path / "index.json").events[0]
    assert (back.species, back.highlights, back.region) == (893, ("Shiny",), "Ocidente")
```

Run: `$PY -m pytest tests/test_catalog.py -q` → FAIL (`group_events` não existe).

- [ ] **Step 5: Mudanças em `distrib/catalog.py`**

1. Imports: acrescente `from typing import Callable`.
2. `INDEX_VERSION = 2`.
3. Campos novos no fim de `Event` (depois de `sort_key`):

```python
    species: int = 0                            # número nacional; 0 = não é Pokémon
    highlights: tuple[str, ...] = ()            # "Shiny", "Gigantamax", "Nv 60"…
    region: str = ""                            # "Ocidente", "Japão", "ENG"…
```
4. Em `load_index`, o `Event(...)` passa a ler também:

```python
                        species=int(e.get("species", 0)),
                        highlights=tuple(e.get("highlights", ())),
                        region=e.get("region", ""))
```
5. Acrescente depois da classe `Catalog`:

```python
GROUP_NAMES = {"item": "Itens", "extra": "Presentes do pokeldn", "pokemon:0": "Outros"}


@dataclass(frozen=True)
class Group:
    key: str                    # "pokemon:893" | "item" | "extra"
    name: str
    species: int
    events: tuple[Event, ...]
    highlights: tuple[str, ...]


def group_events(events: list[Event], species_name: Callable[[int], str]) -> list[Group]:
    buckets: dict[str, list[Event]] = {}
    for event in sorted(events, key=lambda e: e.sort_key):
        key = f"pokemon:{event.species}" if event.kind == "pokemon" else event.kind
        buckets.setdefault(key, []).append(event)
    groups = []
    for key, members in buckets.items():
        species = members[0].species if key.startswith("pokemon:") else 0
        name = species_name(species) if species else GROUP_NAMES.get(key, key)
        seen: list[str] = []
        for event in members:
            seen += [h for h in event.highlights if h not in seen]
        groups.append(Group(key, name, species, tuple(members), tuple(seen[:3])))
    return sorted(groups, key=lambda g: (g.species == 0, g.key == "extra", normalize(g.name)))


def search_groups(groups: list[Group], text: str) -> list[Group]:
    words = normalize(text).split()
    if not words:
        return groups
    return [g for g in groups
            if all(w in normalize(g.name) or any(w in e.search_text for e in g.events) for w in words)]
```

- [ ] **Step 6: Rodar**

Run: `$PY -m pytest tests/test_catalog.py tests/test_species.py -q`
Expected: passam.

- [ ] **Step 7: Commit**

```bash
git add build/gen_species.py distrib/species_data.py distrib/species.py distrib/catalog.py tests/test_species.py tests/test_catalog.py
git commit -m "Espécies (PokeAPI) e agrupamento dos eventos por Pokémon"
```

---

### Task 8: Jogos no pokeldn v0.5.0 (comandos pelo runner, espécie, destaques, região)

**Files:**
- Modify: `distrib/games/swsh.py`, `distrib/games/frlg.py`, `distrib/runners/frlg_session.py`, `tests/test_swsh.py`, `tests/test_frlg.py`

**Interfaces:**
- Consumes: `runner.command`, `species.gen3_to_national`, logs da Task 2.
- Produces: eventos com `species`, `highlights`, `region` preenchidos; `Job.argv` = `runner.command(...)`; `Job.cwd = str(cfg.pokeldn_dir)` nos dois jogos.
  - `swsh.region_of(name: str) -> str`, `swsh.highlights_of(info: dict) -> tuple[str, ...]`

- [ ] **Step 1: Testes que falham**

Em `tests/test_swsh.py`, substitua `test_build_job` e acrescente:

```python
def test_build_job(gallery, cfg):
    from distrib import runner
    event = build(gallery, cfg).search("zarude")[0]
    job = A.build_job(event, cfg, "COM5")
    assert job.env["POKELDN_RADIO"] == "esp32:COM5"
    assert list(job.argv[:len(runner.command())]) == runner.command()
    rest = job.argv[len(runner.command()):]
    assert rest[:2] == ("--run", "bin/swsh_gift_host.py")
    assert "--no-validate" in rest
    assert rest[rest.index("--record") + 1] == str(cfg.catalog_dir / "swsh" / event.files[0])
    assert rest[rest.index("--keys") + 1] == str(cfg.keys)
    assert job.cwd == str(cfg.pokeldn_dir)


def test_catalog_fills_species_highlights_and_region(gallery, cfg):
    zarude = build(gallery, cfg).search("zarude")[0]
    assert zarude.species == 893
    assert "Nv 60" in zarude.highlights
    assert zarude.region == "Ocidente"


def test_region_of():
    assert swsh.region_of("Jungle Zarude (Western Release)") == "Ocidente"
    assert swsh.region_of("ポケセン Eevee (Ver 1. Dynamic PID)") == "Japão"
    assert swsh.region_of("Korean Pikachu") == "Coreia"
    assert swsh.region_of("Item Poke Ball x100") == ""


def test_parse_real_v050_log(fixtures):
    lines = (fixtures / "logs" / "swsh_v050.txt").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    updates = [u for u in map(A.parse_line, lines) if u]
    assert any(u.channel for u in updates)
    assert any(u.state == "on_air" for u in updates)
    assert not any(u.state == "error" for u in updates)
```

Em `tests/test_frlg.py`, substitua `test_build_job_for_pk3_and_extra` e acrescente:

```python
def test_build_job_for_pk3_and_extra(gallery, cfg):
    from distrib import runner
    a = adapter(cfg)
    cat = a.build_catalog(gallery / frlg.FRLG_RAW, cfg)
    job = a.build_job(cat.search("lugia")[0], cfg, "COM5")
    rest = job.argv[len(runner.command()):]
    assert rest[:2] == ("--module", "distrib.runners.frlg_session")
    assert rest[rest.index("--pokeldn") + 1] == str(cfg.pokeldn_dir)
    assert rest[rest.index("--idle-timeout") + 1] == str(cfg.frlg_idle_timeout)
    assert job.env["POKELDN_RADIO"] == "esp32:COM5"
    assert job.cwd == str(cfg.pokeldn_dir)
    extra = cat.get("extra:altering-cave")
    job = a.build_job(extra, cfg, "COM5")
    assert job.argv[job.argv.index("--extra") + 1] == "altering-cave"


def test_catalog_fills_species_and_highlights(gallery, cfg):
    cat = adapter(cfg).build_catalog(gallery / frlg.FRLG_RAW, cfg)
    lugia = cat.search("lugia")[0]
    assert lugia.species == 249
    assert "Nv 70" in lugia.highlights
    assert lugia.region == "ENG"
    assert cat.get("extra:altering-cave").species == 0


def test_parse_real_v050_log(fixtures):
    a = frlg.FrlgAdapter(None)
    lines = (fixtures / "logs" / "frlg_v050.txt").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    states = [u.state for u in map(a.parse_line, lines) if u and u.state]
    assert "on_air" in states and "console" in states and "delivered" in states
    assert "error" not in states
```
(`Tee-Object` do PowerShell 5.1 grava UTF-16; se a leitura acima vier com `\x00`, converta o arquivo uma vez: `$PY -c "import pathlib,sys;p=pathlib.Path(sys.argv[1]);p.write_text(p.read_text(encoding='utf-16'),encoding='utf-8')" tests/fixtures/logs/swsh_v050.txt` e o mesmo para o do FRLG, e faça commit junto.)

Run: `$PY -m pytest tests/test_swsh.py tests/test_frlg.py -q` → FAIL.

- [ ] **Step 2: `distrib/games/swsh.py`**

1. Imports: acrescente `from distrib import runner`.
2. Acrescente depois de `_CHANNEL`:

```python
_JAPANESE = re.compile(r"[぀-ヿ一-鿿]")


def region_of(name: str) -> str:
    low = name.lower()
    if "western" in low:
        return "Ocidente"
    if "korea" in low:
        return "Coreia"
    if any(word in low for word in ("chinese", "taiwan", "hong kong")):
        return "China/Taiwan"
    if "japan" in low or _JAPANESE.search(name):
        return "Japão"
    return ""


def highlights_of(info: dict) -> tuple[str, ...]:
    out = []
    if info["shiny_type"] in (2, 3):
        out.append("Shiny")
    if info["gigantamax"]:
        out.append("Gigantamax")
    if info["level"]:
        out.append(f"Nv {info['level']}")
    return tuple(out)
```
3. No `return Event(...)` de `_event`, acrescente:

```python
                     species=info["species"] if pokemon else 0,
                     highlights=highlights_of(info) if pokemon else (),
                     region=region_of(name))
```
4. `build_job` (substituir):

```python
    def build_job(self, event: Event, cfg: Config, port: str) -> Job:
        record = cfg.catalog_dir / self.game / event.files[0]
        argv = runner.command("--run", "bin/swsh_gift_host.py", "--record", str(record),
                              "--keys", str(cfg.keys), "--seconds", "86400", "--no-validate")
        return Job(argv=tuple(argv), env={"POKELDN_RADIO": f"esp32:{port}"},
                   cwd=str(cfg.pokeldn_dir), label=event.name)
```

- [ ] **Step 3: `distrib/games/frlg.py`**

1. Imports: `from distrib import runner` e `from distrib.species import gen3_to_national`.
2. Em `_event`, troque o `return Event(...)` por:

```python
        highlights = [f"Nv {d['level']}"]
        if shiny == len(files):
            highlights.append("Shiny")
        return Event(game=self.game, key=f"{folder}/{species}/{ot}/{d['language']}", name=name,
                     kind="pokemon", details=details, files=files, sort_key=name,
                     species=gen3_to_national(species), highlights=tuple(highlights),
                     region=language)
```
3. `build_job` (substituir o começo e o `return`):

```python
    def build_job(self, event: Event, cfg: Config, port: str) -> Job:
        argv = ["--module", "distrib.runners.frlg_session", "--pokeldn", str(cfg.pokeldn_dir)]
        on_delivered = None
        if event.kind == "extra":
            argv += ["--extra", event.key.removeprefix("extra:")]
        else:
            argv += ["--pk3", str(cfg.catalog_dir / self.game / self.rotation.peek(event))]
            on_delivered = lambda: self.rotation.advance(event)
        argv += ["--keys", str(cfg.keys), "--phy", "auto",
                 "--idle-timeout", str(cfg.frlg_idle_timeout)]
        return Job(argv=tuple(runner.command(*argv)), env={"POKELDN_RADIO": f"esp32:{port}"},
                   cwd=str(cfg.pokeldn_dir), label=event.name, on_delivered=on_delivered)
```

- [ ] **Step 4: `distrib/runners/frlg_session.py`** — `load_host` põe `bin/` no `sys.path` (o host importa módulos vizinhos):

```python
def load_host(pokeldn_dir: Path):
    bin_dir = str(pokeldn_dir / "bin")
    if bin_dir not in sys.path:
        sys.path.insert(0, bin_dir)
    spec = importlib.util.spec_from_file_location("frlg_mg_host", pokeldn_dir / "bin" / "frlg_mg_host.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
```
Atualize a docstring do módulo: troque "(rodar como root)" por "(processo-filho do app)".

- [ ] **Step 5: Rodar tudo**

Run: `$PY -m pytest -q`
Expected: só podem falhar `tests/test_config_valor.py` e os de `windows/tests` (somem na Task 17). Se `test_runner_registers_before_the_host_parser` (test_frlg_gift) falhar, o `frlg_mg_host.py` do v0.5.0 mudou a forma de montar o parser: leia `vendor/pokeldn/bin/frlg_mg_host.py` (`build_parser`, `main`) e ajuste só `frlg_session.main` até o teste passar.

- [ ] **Step 6: Commit**

```bash
git add distrib/games distrib/runners/frlg_session.py tests/test_swsh.py tests/test_frlg.py tests/fixtures/logs
git commit -m "Jogos no pokeldn v0.5.0: comandos pelo runner, espécie, destaques e região"
```

---

### Task 9: Cache de sprites

**Files:**
- Create: `distrib/sprites.py`, `tests/test_sprites.py`

**Interfaces:**
- Produces: `SpriteCache(folder: Path, opener=urllib.request.urlopen, clock=time.monotonic)` com `cached(species: int) -> Path | None` e `get(species: int) -> Path | None` (baixa se faltar; nunca levanta erro).

- [ ] **Step 1: Testes que falham — `tests/test_sprites.py`**

```python
import io
import urllib.error

from distrib.sprites import PNG, SpriteCache

IMAGE = PNG + b"\x00" * 50


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_downloads_once_and_caches(tmp_path):
    calls = []

    def opener(url, timeout):
        calls.append(url)
        return Resp(IMAGE)

    cache = SpriteCache(tmp_path, opener=opener)
    assert cache.cached(25) is None
    path = cache.get(25)
    assert path == tmp_path / "25.png" and path.read_bytes() == IMAGE
    assert cache.get(25) == path
    assert calls == ["https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png"]


def test_404_is_remembered(tmp_path):
    calls = []

    def opener(url, timeout):
        calls.append(url)
        raise urllib.error.HTTPError(url, 404, "nf", None, None)

    cache = SpriteCache(tmp_path, opener=opener)
    assert cache.get(9999) is None and cache.get(9999) is None
    assert len(calls) == 1


def test_offline_returns_none_and_cools_down(tmp_path):
    now = [0.0]
    calls = []

    def opener(url, timeout):
        calls.append(url)
        raise urllib.error.URLError("offline")

    cache = SpriteCache(tmp_path, opener=opener, clock=lambda: now[0])
    assert cache.get(1) is None and cache.get(2) is None
    assert len(calls) == 1
    now[0] = 61.0
    assert cache.get(2) is None and len(calls) == 2


def test_rejects_non_png_and_species_zero(tmp_path):
    cache = SpriteCache(tmp_path, opener=lambda url, timeout: Resp(b"<html>"))
    assert cache.get(5) is None
    assert cache.get(0) is None
```

Run: `$PY -m pytest tests/test_sprites.py -q` → FAIL.

- [ ] **Step 2: `distrib/sprites.py`**

```python
"""Sprites dos Pokémon (repositório de sprites do PokeAPI) num cache local. Nunca levanta erro."""
from __future__ import annotations

import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon"
PNG = b"\x89PNG\r\n\x1a\n"
MAX_BYTES = 200_000
OFFLINE_COOLDOWN = 60.0


class SpriteCache:
    def __init__(self, folder: Path, opener=urllib.request.urlopen, clock=time.monotonic):
        self.folder, self.opener, self.clock = folder, opener, clock
        self._offline_until = 0.0
        self._lock = threading.Lock()

    def cached(self, species: int) -> Path | None:
        path = self.folder / f"{species}.png"
        return path if species > 0 and path.exists() else None

    def get(self, species: int) -> Path | None:
        if species <= 0:
            return None
        if (path := self.cached(species)) is not None:
            return path
        missing = self.folder / f"{species}.missing"
        with self._lock:
            if missing.exists() or self.clock() < self._offline_until:
                return None
            try:
                with self.opener(f"{BASE}/{species}.png", timeout=5) as resp:
                    data = resp.read(MAX_BYTES + 1)
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    self.folder.mkdir(parents=True, exist_ok=True)
                    missing.touch()
                return None
            except (OSError, ValueError):
                self._offline_until = self.clock() + OFFLINE_COOLDOWN
                return None
            if not data.startswith(PNG) or len(data) > MAX_BYTES:
                return None
            self.folder.mkdir(parents=True, exist_ok=True)
            tmp = self.folder / f"{species}.tmp"
            tmp.write_bytes(data)
            tmp.replace(self.folder / f"{species}.png")
            return self.folder / f"{species}.png"
```

- [ ] **Step 3: Rodar e commit**

```bash
$PY -m pytest tests/test_sprites.py -q
git add distrib/sprites.py tests/test_sprites.py
git commit -m "Cache de sprites do PokeAPI"
```
Expected: 4 passed.

---

### Task 10: Preparar a placa (gravar o firmware com esptool)

**Files:**
- Create: `distrib/board.py`, `distrib/runners/flash.py`, `tests/test_board.py`

**Interfaces:**
- Consumes: `runner.command`, `runner.child_env`, `runner.popen_kwargs`, `Config.firmware_dir`.
- Produces:
  - `board.FIRMWARE: dict[str, str]` (nome do chip do esptool → arquivo), `board.CHIP_ARG: dict[str, str]`
  - `board.BoardError`
  - `board.firmware_for(chip: str, firmware_dir: Path) -> Path`
  - `board.parse_progress(line: str) -> float | None` (0.0–1.0)
  - `board.flash(port: str, cfg: Config, on_line: Callable[[str], None], on_progress: Callable[[float], None], popen=subprocess.Popen) -> int` (código de saída; bloqueia)
  - `python main.py --module distrib.runners.flash COM5 <pasta dos firmwares>`

- [ ] **Step 1: Testes que falham — `tests/test_board.py`**

```python
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
```

Run: `$PY -m pytest tests/test_board.py -q` → FAIL.

- [ ] **Step 2: `distrib/board.py`**

```python
"""Preparar a placa: escolher o firmware do pokeldn pelo chip e gravar num processo-filho."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Callable

from distrib import runner
from distrib.config import Config

FIRMWARE = {
    "ESP32": "pokeldn-radio.bin",
    "ESP32-S3": "pokeldn-radio-s3.bin",
    "ESP32-C3": "pokeldn-radio-c3.bin",
    "ESP32-C6": "pokeldn-radio-c6.bin",
}
CHIP_ARG = {"ESP32": "esp32", "ESP32-S3": "esp32s3", "ESP32-C3": "esp32c3", "ESP32-C6": "esp32c6"}
_PERCENT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s?%")


class BoardError(Exception):
    pass


def firmware_for(chip: str, firmware_dir: Path) -> Path:
    name = FIRMWARE.get(chip)
    if name is None:
        raise BoardError(f"{chip} não é suportado. Use ESP32, ESP32-S3, ESP32-C3 ou ESP32-C6.")
    path = firmware_dir / name
    if not path.is_file():
        raise BoardError(f"Falta o firmware {name} em {firmware_dir}")
    return path


def parse_progress(line: str) -> float | None:
    if "Writing at" not in line:
        return None
    match = _PERCENT.search(line)
    return min(float(match.group(1)), 100.0) / 100 if match else None


def flash(port: str, cfg: Config, on_line: Callable[[str], None],
          on_progress: Callable[[float], None], popen=subprocess.Popen) -> int:
    kwargs = {**runner.popen_kwargs(), "stdin": subprocess.DEVNULL}
    proc = popen(runner.command("--module", "distrib.runners.flash", port, str(cfg.firmware_dir)),
                 cwd=str(cfg.pokeldn_dir), env=runner.child_env(managed=False), **kwargs)
    for line in proc.stdout:
        line = line.rstrip("\n")
        on_line(line)
        if (value := parse_progress(line)) is not None:
            on_progress(value)
    return proc.wait()
```

- [ ] **Step 3: `distrib/runners/flash.py`**

```python
"""Grava o firmware do pokeldn: python main.py --module distrib.runners.flash COM5 PASTA"""
import sys
from pathlib import Path

import esptool

from distrib.board import CHIP_ARG, BoardError, firmware_for


def main(argv=None) -> int:
    port, folder = (argv if argv is not None else sys.argv[1:])[:2]
    with esptool.detect_chip(port, connect_attempts=2) as chip:
        name = chip.CHIP_NAME
    print(f"[flash] chip {name}", flush=True)
    try:
        path = firmware_for(name, Path(folder))
    except BoardError as exc:
        print(f"[flash] erro: {exc}", flush=True)
        return 2
    esptool.main(["--chip", CHIP_ARG[name], "--port", port, "--baud", "460800",
                  "--after", "hard-reset", "write-flash", "0x0", str(path)])
    print("[flash] ok", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Rodar e commit**

```bash
$PY -m pytest tests/test_board.py -q
git add distrib/board.py distrib/runners/flash.py tests/test_board.py
git commit -m "Preparar placa: firmware do pokeldn pelo chip, gravado com esptool"
```
Expected: 3 passed. (A gravação real é testada na Task 18.)

---

### Task 11: Atualização automática pelo GitHub Releases

**Files:**
- Create: `distrib/update.py`, `tests/test_update.py`
- Modify: `distrib/__init__.py`

**Interfaces:**
- Produces:
  - `distrib.__version__ = "2.0.0"`
  - `update.REPO`, `update.API`, `update.ASSET = "Distribuidor.exe"`
  - `update.Release(tag: str, version: tuple[int, ...], url: str, size: int, sha256: str)`, `update.UpdateError`
  - `update.parse_version(text: str) -> tuple[int, ...]`
  - `update.latest(opener=urllib.request.urlopen) -> Release | None`
  - `update.newer(release: Release | None, current: str) -> bool`
  - `update.download(release: Release, folder: Path, opener=urllib.request.urlopen) -> Path`
  - `update.apply(new_exe: Path, exe: Path, launch=subprocess.Popen) -> None`
  - `update.cleanup(exe: Path) -> None`

- [ ] **Step 1: `distrib/__init__.py`** — conteúdo: `__version__ = "2.0.0"` (mais uma linha em branco).

- [ ] **Step 2: Testes que falham — `tests/test_update.py`**

```python
import hashlib
import io
import json
import shutil

import pytest

from distrib import update

BODY = b"novo exe" * 100
SHA = hashlib.sha256(BODY).hexdigest()


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
```

Run: `$PY -m pytest tests/test_update.py -q` → FAIL.

- [ ] **Step 3: `distrib/update.py`**

```python
"""Atualização automática pelo GitHub Releases: achar, baixar (conferindo o SHA-256) e trocar o .exe.

O Windows não deixa sobrescrever um .exe aberto, mas deixa renomeá-lo: o atual vira
Distribuidor.exe.old, o novo assume o nome e é aberto; a próxima abertura apaga o .old.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO = "Carlos-Gabryel/pokeldn-distrib"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET = "Distribuidor.exe"
HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "Distribuidor"}


class UpdateError(Exception):
    pass


@dataclass(frozen=True)
class Release:
    tag: str
    version: tuple[int, ...]
    url: str
    size: int
    sha256: str


def parse_version(text: str) -> tuple[int, ...]:
    match = re.fullmatch(r"v?(\d+(?:\.\d+)*)", text.strip())
    if not match:
        raise UpdateError(f"versão inválida: {text!r}")
    return tuple(int(part) for part in match.group(1).split("."))


def latest(opener=urllib.request.urlopen) -> Release | None:
    with opener(urllib.request.Request(API, headers=HEADERS), timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    for asset in data.get("assets", []):
        if asset.get("name") != ASSET:
            continue
        digest = asset.get("digest") or ""
        if not digest.startswith("sha256:"):
            raise UpdateError("o Release não publica o SHA-256 do .exe")
        return Release(data["tag_name"], parse_version(data["tag_name"]),
                       asset["browser_download_url"], int(asset["size"]), digest.removeprefix("sha256:"))
    return None


def newer(release: Release | None, current: str) -> bool:
    return release is not None and release.version > parse_version(current)


def download(release: Release, folder: Path, opener=urllib.request.urlopen) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    part = folder / (ASSET + ".part")
    digest, size = hashlib.sha256(), 0
    request = urllib.request.Request(release.url, headers={"User-Agent": "Distribuidor"})
    with opener(request, timeout=60) as resp, open(part, "wb") as out:
        while chunk := resp.read(1 << 16):
            digest.update(chunk)
            out.write(chunk)
            size += len(chunk)
    if size != release.size or digest.hexdigest() != release.sha256.lower():
        part.unlink(missing_ok=True)
        raise UpdateError("o download não confere (tamanho ou SHA-256)")
    ready = folder / f"Distribuidor-{release.tag}.exe"
    part.replace(ready)
    return ready


def apply(new_exe: Path, exe: Path, launch=subprocess.Popen) -> None:
    old = exe.with_name(exe.name + ".old")
    old.unlink(missing_ok=True)
    exe.rename(old)
    try:
        shutil.move(str(new_exe), str(exe))
    except OSError:
        old.rename(exe)
        raise
    launch([str(exe)], close_fds=True)


def cleanup(exe: Path) -> None:
    try:
        exe.with_name(exe.name + ".old").unlink(missing_ok=True)
    except OSError:
        pass        # a versão anterior ainda está fechando; fica para a próxima abertura
```

- [ ] **Step 4: Rodar e commit**

```bash
$PY -m pytest tests/test_update.py -q
git add distrib/__init__.py distrib/update.py tests/test_update.py
git commit -m "Atualização automática pelo GitHub Releases (SHA-256, troca segura do .exe)"
```
Expected: 5 passed.

---

### Task 12: Serviço (fachada que a interface usa)

**Files:**
- Create: `distrib/service.py`, `tests/test_service.py`

**Interfaces:**
- Consumes: tudo das Tasks 3–11.
- Produces (a interface da Task 13+ usa só isto):
  - `BoardInfo(kind="checking", port=None, bridge="", message=...)` com `.ok`; `kind` ∈ `checking | ready | none | many | busy | silent | flashing`
  - `RunInfo(game, event, state="starting", since=None, channel=None, deliveries=0, last_event="", detail="")`
  - `Snapshot(board, keys_ok, catalog_ok, run, log, flash_progress, update_state, update_version)` com `.ready`; `update_state` ∈ `none | downloading | ready | error`
  - `Service(cfg, adapters=None, *, comports=None, hello=None, make_distributor=None, sprites=None, latest=update.latest, download=update.download, exe_path=None, clock=time.monotonic)`
  - métodos: `snapshot()`, `subscribe(cb)`, `set_keys(path)`, `download_catalog(log)`, `event_count(game)`, `groups(game, text="")`, `start(game, event)`, `pause()`, `resume()`, `stop()`, `check_board(force=False)`, `flash_board() -> int`, `check_update()`, `apply_update() -> bool`, `start_background(updates: bool)`, `shutdown()`; atributos `cfg`, `adapters`, `sprites`.
  - `start`, `stop`, `flash_board`, `download_catalog`, `check_update` **bloqueiam**: a interface chama em thread.

- [ ] **Step 1: Testes que falham — `tests/test_service.py`**

```python
from types import SimpleNamespace as NS

import pytest

from distrib import radio, update
from distrib.catalog import Catalog, Event, save_index
from distrib.distributor import Status
from distrib.service import Service

KEYS = "".join(f"key_{i:02d} = {'ab' * 16}\n" for i in range(12))


def ev(key, species):
    return Event(game="swsh", key=key, name=key, kind="pokemon", details=(), files=(key,),
                 sort_key=key, species=species)


class FakeDistributor:
    def __init__(self):
        self.calls, self._status = [], Status(state="starting")

    def start(self):
        self.calls.append("start")

    def stop(self):
        self.calls.append("stop")

    def pause(self):
        self.calls.append("pause")

    def resume(self):
        self.calls.append("resume")

    def status(self):
        return self._status


def make(cfg, boards=(("COM5", 0x1A86, 0x55D4),), hello=None, **kw):
    state = {"boards": list(boards), "hello": 0}

    def comports():
        return [NS(device=d, vid=v, pid=p) for d, v, p in state["boards"]]

    def fake_hello(port):
        state["hello"] += 1
        if hello:
            return hello(port)
        return "ESP32 pokeldn radio"

    for game in ("swsh", "frlg"):
        save_index(Catalog(game, [ev(f"{game}-a", 25), ev(f"{game}-b", 893)]),
                   cfg.catalog_dir / game / "index.json")
    fakes = []

    def make_distributor(game, event):
        fakes.append(FakeDistributor())
        return fakes[-1]

    svc = Service(cfg, comports=comports, hello=fake_hello, make_distributor=make_distributor, **kw)
    return svc, state, fakes


def ready(svc, cfg):
    cfg.keys.parent.mkdir(parents=True, exist_ok=True)
    cfg.keys.write_text(KEYS, encoding="utf-8")
    svc.set_keys(cfg.keys)
    svc.check_board()


def test_initial_snapshot_and_subscribe(cfg):
    svc, _, _ = make(cfg)
    seen = []
    svc.subscribe(seen.append)
    assert seen[0].catalog_ok and not seen[0].keys_ok and not seen[0].ready
    svc.check_board()
    assert seen[-1].board.kind == "ready" and seen[-1].board.port == "COM5"


def test_set_keys_rejects_binary_and_keeps_the_old_file(cfg, tmp_path):
    svc, _, _ = make(cfg)
    good = tmp_path / "prod.keys"
    good.write_text(KEYS, encoding="utf-8")
    svc.set_keys(good)
    assert cfg.keys.read_text(encoding="utf-8") == KEYS and svc.snapshot().keys_ok
    bad = tmp_path / "lixo.keys"
    bad.write_bytes(b"\x00\xff" * 500)
    with pytest.raises(ValueError, match="prod.keys"):
        svc.set_keys(bad)
    assert cfg.keys.read_text(encoding="utf-8") == KEYS


def test_board_states(cfg):
    svc, state, _ = make(cfg, boards=())
    svc.check_board()
    assert svc.snapshot().board.kind == "none"
    state["boards"] = [("COM5", 0x1A86, 0x55D4), ("COM7", 0x10C4, 0xEA60)]
    svc.check_board()
    assert svc.snapshot().board.kind == "many"


def test_board_busy_and_silent(cfg):
    def busy(port):
        raise radio.RadioError("HELLO falhou em COM5: PermissionError: Access is denied")

    svc, _, _ = make(cfg, hello=busy)
    svc.check_board()
    assert svc.snapshot().board.kind == "busy"

    def silent(port):
        raise radio.RadioError("a placa em COM5 não respondeu em 20 s")

    svc, _, _ = make(cfg, hello=silent)
    svc.check_board()
    assert svc.snapshot().board.kind == "silent"


def test_board_port_change_triggers_new_hello(cfg):
    svc, state, _ = make(cfg)
    svc.check_board()
    svc.check_board()
    assert state["hello"] == 1
    state["boards"] = [("COM8", 0x1A86, 0x55D4)]
    svc.check_board()
    assert state["hello"] == 2 and svc.snapshot().board.port == "COM8"
    svc.check_board(force=True)
    assert state["hello"] == 3


def test_groups_and_search(cfg):
    svc, _, _ = make(cfg)
    assert [g.name for g in svc.groups("swsh")] == ["Pikachu", "Zarude"]
    assert [g.name for g in svc.groups("swsh", "zaru")] == ["Zarude"]
    assert svc.event_count("frlg") == 2


def test_start_requires_ready_then_runs(cfg):
    svc, _, fakes = make(cfg)
    event = svc.groups("swsh")[0].events[0]
    with pytest.raises(RuntimeError):
        svc.start("swsh", event)
    ready(svc, cfg)
    svc.start("swsh", event)
    assert fakes[0].calls == ["start"]
    assert svc.snapshot().run.event == event
    fakes[0]._status = Status(state="on_air", since=1.0, channel=6)
    svc._sync_run()
    assert svc.snapshot().run.state == "on_air" and svc.snapshot().run.channel == 6
    svc.pause()
    svc.resume()
    svc.stop()
    assert fakes[0].calls == ["start", "pause", "resume", "stop"]
    assert svc.snapshot().run is None


def test_lost_board_during_run(cfg):
    svc, _, fakes = make(cfg)
    ready(svc, cfg)
    svc.start("swsh", svc.groups("swsh")[0].events[0])
    fakes[0]._status = Status(state="no_board")
    svc._sync_run()
    svc.check_board()
    assert svc.snapshot().board.kind == "none"
    assert "continua" in svc.snapshot().board.message


def test_shutdown_stops_the_distribution(cfg):
    svc, _, fakes = make(cfg)
    ready(svc, cfg)
    svc.start("swsh", svc.groups("swsh")[0].events[0])
    svc.shutdown()
    assert fakes[0].calls[-1] == "stop"


def test_flash_refused_during_run(cfg):
    svc, _, _ = make(cfg)
    ready(svc, cfg)
    svc.start("swsh", svc.groups("swsh")[0].events[0])
    with pytest.raises(RuntimeError):
        svc.flash_board()


def test_check_update_downloads_and_apply_needs_exe(cfg, tmp_path):
    rel = update.Release("v9.0.0", (9, 0, 0), "u", 1, "x")
    got = tmp_path / "novo.exe"
    got.write_bytes(b"n")
    svc, _, _ = make(cfg, latest=lambda: rel, download=lambda r, folder: got)
    svc.check_update()
    assert svc.snapshot().update_state == "ready" and svc.snapshot().update_version == "v9.0.0"
    assert svc.apply_update() is False          # sem exe_path (desenvolvimento)


def test_apply_update_error_is_reported(cfg, tmp_path, monkeypatch):
    rel = update.Release("v9.0.0", (9, 0, 0), "u", 1, "x")
    got = tmp_path / "novo.exe"
    got.write_bytes(b"n")
    exe = tmp_path / "Distribuidor.exe"
    exe.write_bytes(b"v")
    svc, _, _ = make(cfg, latest=lambda: rel, download=lambda r, folder: got, exe_path=exe)
    svc.check_update()

    def boom(new, current):
        raise PermissionError("sem permissão")

    monkeypatch.setattr(update, "apply", boom)
    assert svc.apply_update() is False
    assert svc.snapshot().update_state == "error"


def test_no_update_when_offline(cfg):
    def offline():
        raise OSError("offline")

    svc, _, _ = make(cfg, latest=offline)
    svc.check_update()
    assert svc.snapshot().update_state == "none"
```

Run: `$PY -m pytest tests/test_service.py -q` → FAIL.

- [ ] **Step 2: `distrib/service.py`**

```python
"""A fachada que a interface usa: estado observável (Snapshot) + ações. Nada de Flet aqui.

As ações que bloqueiam (start, stop, flash_board, download_catalog, check_update) são chamadas
pela interface numa thread. Cada mudança de estado vira um Snapshot novo entregue aos inscritos,
de qualquer thread.
"""
from __future__ import annotations

import re
import shutil
import threading
import time
import traceback
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Callable

from distrib import __version__, board, radio, update
from distrib.catalog import Catalog, Event, Group, group_events, load_index, search_groups
from distrib.config import Config
from distrib.distributor import Distributor
from distrib.species import name as species_name
from distrib.sprites import SpriteCache

_KEY_LINE = re.compile(r"^\s*\w+\s*=\s*[0-9a-fA-F]+\s*$")
LOG_LINES = 300
BOARD_POLL = 2.0
RUN_POLL = 0.5
UPDATE_EVERY = 6 * 3600
BUSY_HINTS = ("PermissionError", "Access is denied", "Acesso negado", "could not open port")

MSG_NONE = "Plugue a placa no USB. Se ela já está plugada, instale o driver na aba Placa."
MSG_MANY = "Há mais de uma placa plugada. Deixe só a do Distribuidor."
MSG_BUSY = "Outro programa está usando a {port}. Feche-o e replugue a placa."
MSG_SILENT = "A placa em {port} não respondeu. Use “Preparar placa” na aba Placa."
MSG_LOST = "Placa desconectada. Reconecte o cabo USB; a distribuição continua quando ela voltar."


@dataclass(frozen=True)
class BoardInfo:
    kind: str = "checking"
    port: str | None = None
    bridge: str = ""
    message: str = "Procurando a placa…"

    @property
    def ok(self) -> bool:
        return self.kind == "ready"


@dataclass(frozen=True)
class RunInfo:
    game: str
    event: Event
    state: str = "starting"
    since: float | None = None
    channel: int | None = None
    deliveries: int = 0
    last_event: str = ""
    detail: str = ""


@dataclass(frozen=True)
class Snapshot:
    board: BoardInfo = BoardInfo()
    keys_ok: bool = False
    catalog_ok: bool = False
    run: RunInfo | None = None
    log: tuple[str, ...] = ()
    flash_progress: float | None = None
    update_state: str = "none"
    update_version: str = ""

    @property
    def ready(self) -> bool:
        return self.keys_ok and self.catalog_ok and self.board.ok


class Service:
    def __init__(self, cfg: Config, adapters: dict | None = None, *, comports=None, hello=None,
                 make_distributor=None, sprites: SpriteCache | None = None,
                 latest=update.latest, download=update.download, exe_path: Path | None = None,
                 clock=time.monotonic):
        if adapters is None:
            from distrib.games import ADAPTERS as adapters
        if comports is None:
            from serial.tools import list_ports
            comports = list_ports.comports
        self.cfg, self.adapters, self.clock = cfg, adapters, clock
        self.comports = comports
        self.hello = hello or (lambda port: radio.hello(port, cfg))
        self.make_distributor = make_distributor or self._default_distributor
        self.sprites = sprites or SpriteCache(cfg.sprites_dir)
        self._latest, self._download, self.exe_path = latest, download, exe_path
        self._lock = threading.RLock()
        self._listeners: list[Callable[[Snapshot], None]] = []
        self._catalogs: dict[str, Catalog] = {}
        self._groups: dict[str, list[Group]] = {}
        self._distributor: Distributor | None = None
        self._log: list[str] = []
        self._ready_update: Path | None = None
        self._last_port: str | None = None
        self._stop = threading.Event()
        self._snap = Snapshot(keys_ok=self._keys_valid(cfg.keys), catalog_ok=self._load_catalogs())

    # ---- estado ----
    def snapshot(self) -> Snapshot:
        with self._lock:
            return self._snap

    def subscribe(self, callback: Callable[[Snapshot], None]) -> None:
        with self._lock:
            self._listeners.append(callback)
        callback(self.snapshot())

    def _publish(self, **changes) -> None:
        with self._lock:
            new = replace(self._snap, **changes)
            if new == self._snap:
                return
            self._snap = new
            listeners = list(self._listeners)
        for callback in listeners:
            try:
                callback(new)
            except Exception:
                traceback.print_exc()       # uma tela com defeito não derruba o serviço

    # ---- configuração ----
    @staticmethod
    def _keys_valid(path: Path) -> bool:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return False
        return sum(1 for line in lines if _KEY_LINE.match(line)) >= 10

    def set_keys(self, source: Path) -> None:
        if not self._keys_valid(source):
            raise ValueError("Esse arquivo não parece um prod.keys "
                             "(esperado: linhas 'nome = hexadecimal').")
        self.cfg.keys.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != self.cfg.keys.resolve():
            shutil.copyfile(source, self.cfg.keys)
        self._publish(keys_ok=True)

    def _load_catalogs(self) -> bool:
        for game in self.adapters:
            catalog = load_index(game, self.cfg.catalog_dir / game / "index.json")
            self._catalogs[game] = catalog
            self._groups[game] = group_events(catalog.events, species_name)
        return all(self._catalogs[game].events for game in self.adapters)

    def download_catalog(self, log: Callable[[str], None]) -> None:
        from distrib import download
        download.update_catalogs(self.cfg, tuple(self.adapters), log=log)
        self._publish(catalog_ok=self._load_catalogs())

    def event_count(self, game: str) -> int:
        return len(self._catalogs[game].events)

    def groups(self, game: str, text: str = "") -> list[Group]:
        return search_groups(self._groups[game], text)

    # ---- distribuição ----
    def _default_distributor(self, game: str, event: Event) -> Distributor:
        adapter = self.adapters[game]
        log = self.cfg.logs_dir / f"{date.today():%Y-%m-%d}.log"
        return Distributor(adapter.mode, adapter.parse_line,
                           lambda port: adapter.build_job(event, self.cfg, port), log,
                           lambda: radio.find_port(self.comports), on_line=self._append_log)

    def _append_log(self, line: str) -> None:
        with self._lock:
            self._log.append(line)
            del self._log[:-LOG_LINES]
            log = tuple(self._log)
        self._publish(log=log)

    def start(self, game: str, event: Event) -> None:
        if not self.snapshot().ready:
            raise RuntimeError("configuração incompleta")
        self.stop()
        with self._lock:
            self._log.clear()
        self._distributor = self.make_distributor(game, event)
        self._publish(run=RunInfo(game, event), log=())
        self._distributor.start()

    def pause(self) -> None:
        if self._distributor is not None:
            self._distributor.pause()
            self._sync_run()

    def resume(self) -> None:
        if self._distributor is not None:
            self._distributor.resume()
            self._sync_run()

    def stop(self) -> None:
        distributor, self._distributor = self._distributor, None
        if distributor is not None:
            distributor.stop()
        self._publish(run=None)

    def _sync_run(self) -> None:
        distributor, run = self._distributor, self.snapshot().run
        if distributor is None or run is None:
            return
        st = distributor.status()
        self._publish(run=replace(run, state=st.state, since=st.since, channel=st.channel,
                                  deliveries=st.deliveries, last_event=st.last_event,
                                  detail=st.detail))

    # ---- placa ----
    def check_board(self, force: bool = False) -> None:
        snap = self.snapshot()
        if snap.flash_progress is not None:
            return
        if snap.run is not None:
            if snap.run.state == "no_board":
                self._last_port = None
                self._publish(board=BoardInfo("none", message=MSG_LOST))
            elif not snap.board.ok:
                port = radio.find_port(self.comports)
                self._publish(board=BoardInfo("ready", port, snap.board.bridge, "Em uso pela distribuição"))
            return
        boards = radio.list_boards(self.comports)
        if not boards:
            self._last_port = None
            self._publish(board=BoardInfo("none", message=MSG_NONE))
            return
        if len(boards) > 1:
            self._last_port = None
            self._publish(board=BoardInfo("many", message=MSG_MANY))
            return
        port = boards[0]
        if port.device == self._last_port and not force:
            return
        self._last_port = port.device
        self._publish(board=BoardInfo("checking", port.device, port.bridge,
                                      f"Conversando com a placa em {port.device}…"))
        try:
            text = self.hello(port.device)
        except radio.RadioError as exc:
            busy = any(hint in str(exc) for hint in BUSY_HINTS)
            message = (MSG_BUSY if busy else MSG_SILENT).format(port=port.device)
            self._publish(board=BoardInfo("busy" if busy else "silent", port.device, port.bridge, message))
            return
        self._publish(board=BoardInfo("ready", port.device, port.bridge,
                                      f"{port.bridge} · {port.device} · {text}"))

    def flash_board(self) -> int:
        if self.snapshot().run is not None:
            raise RuntimeError("Pare a distribuição antes de preparar a placa.")
        boards = radio.list_boards(self.comports)
        if len(boards) != 1:
            raise RuntimeError(MSG_NONE if not boards else MSG_MANY)
        port = boards[0]
        with self._lock:
            self._log.clear()
        self._publish(flash_progress=0.0, log=(),
                      board=BoardInfo("flashing", port.device, port.bridge, "Gravando o firmware…"))
        try:
            code = board.flash(port.device, self.cfg, self._append_log,
                               lambda value: self._publish(flash_progress=value))
        finally:
            self._publish(flash_progress=None)
        self._last_port = None
        self.check_board(force=True)
        return code

    # ---- atualização ----
    def check_update(self) -> None:
        if self.snapshot().update_state in ("downloading", "ready"):
            return
        try:
            release = self._latest()
            if not update.newer(release, __version__):
                return
            self._publish(update_state="downloading", update_version=release.tag)
            self._ready_update = self._download(release, self.cfg.data_dir / "updates")
            self._publish(update_state="ready")
        except (OSError, ValueError, update.UpdateError):
            downloading = self.snapshot().update_state == "downloading"
            self._publish(update_state="error" if downloading else "none")

    def apply_update(self) -> bool:
        """True quando a versão nova já foi aberta e este app deve fechar."""
        if self._ready_update is None or self.exe_path is None or self.snapshot().run is not None:
            return False
        try:
            update.apply(self._ready_update, self.exe_path)
        except OSError:
            self._publish(update_state="error")
            return False
        return True

    # ---- ciclo de vida ----
    def start_background(self, updates: bool) -> None:
        threading.Thread(target=self._board_loop, daemon=True).start()
        if updates:
            threading.Thread(target=self._update_loop, daemon=True).start()

    def _board_loop(self) -> None:
        next_board = 0.0
        while not self._stop.is_set():
            try:
                self._sync_run()
                if self.clock() >= next_board:
                    self.check_board()
                    next_board = self.clock() + BOARD_POLL
            except Exception:
                traceback.print_exc()
            self._stop.wait(RUN_POLL)

    def _update_loop(self) -> None:
        while not self._stop.is_set():
            self.check_update()
            self._stop.wait(UPDATE_EVERY)

    def shutdown(self) -> None:
        self._stop.set()
        self.stop()
```

- [ ] **Step 3: Rodar**

Run: `$PY -m pytest tests/test_service.py -q && $PY -m pytest -q`
Expected: `test_service.py` passa; a suíte toda só pode falhar em `tests/test_config_valor.py` / `windows/tests`.

- [ ] **Step 4: Commit**

```bash
git add distrib/service.py tests/test_service.py
git commit -m "Service: fachada com Snapshot observável para a interface"
```

---

### Task 13: Interface — tema, assets e a janela com barra lateral

**Files:**
- Create: `build/fetch_icons.py`, `ui/__init__.py`, `ui/views/__init__.py`, `ui/theme.py`, `ui/sprites.py`, `ui/app.py`, `ui/assets/pokeball.svg`, `ui/assets/icons/*.svg` (gerados), `ui/assets/icons/LICENSE`, `ui/views/placeholder.py`

**Interfaces:**
- Consumes: `Service`, `Snapshot`, `BoardInfo`, `config.load/resource_root`, `update.cleanup`.
- Produces:
  - `ui.theme`: tokens `BG SIDEBAR CARD FIELD HOVER BORDER TEXT MUTED FAINT ACCENT GREEN AMBER RADIUS RADIUS_SMALL GAP SIDEBAR_WIDTH CONTROL_HEIGHT`; funções `text, muted, icon, border, card, button, dot, board_card, brand, nav_item, crumbs, stat, apply_page`.
  - `ui.sprites.SpriteSlots(shell, size)` com `.box(species) -> ft.Container` e `.load()`.
  - `ui.app.Shell(page, service)`: atributos `page, service, picker, launcher`; métodos `ui(fn)`, `in_thread(fn, *args)`, `navigate(key)`, `toast(msg)`, `render()`. Cada view tem `control: ft.Control`, `show(snap)` (ao entrar) e `update(snap)` (a cada Snapshot).
  - `ui.app.run()` (chamado por `main.py`).

- [ ] **Step 1: Ícones Lucide — `build/fetch_icons.py`**

```python
"""Baixa os ícones Lucide usados pela interface (licença ISC) para ui/assets/icons/."""
import urllib.request
from pathlib import Path

VERSION = "1.50.0"
BASE = f"https://unpkg.com/lucide-static@{VERSION}"
NAMES = ("gamepad-2", "cpu", "settings", "search", "play", "pause", "square", "download",
         "key-round", "usb", "refresh-cw", "folder-open", "external-link", "check",
         "triangle-alert", "package", "zap")
OUT = Path(__file__).resolve().parent.parent / "ui" / "assets" / "icons"


def get(path: str) -> bytes:
    with urllib.request.urlopen(f"{BASE}/{path}", timeout=30) as resp:
        return resp.read()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        (OUT / f"{name}.svg").write_bytes(get(f"icons/{name}.svg"))
    (OUT / "LICENSE").write_bytes(get("LICENSE"))
    print(f"{len(NAMES)} ícones em {OUT}")


if __name__ == "__main__":
    main()
```
Run: `$PY build/fetch_icons.py` → `17 ícones em ...`. Se algum nome der 404, procure o nome atual em `https://lucide.dev/icons` e troque em `NAMES` e no código que o usa.

- [ ] **Step 2: `ui/assets/pokeball.svg` (desenho nosso)**

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10.5" fill="#F4F5F7"/><path d="M1.5 12a10.5 10.5 0 0 1 21 0z" fill="#E8445A"/><rect x="1.5" y="11" width="21" height="2" fill="#0E0F12"/><circle cx="12" cy="12" r="3.6" fill="#F4F5F7" stroke="#0E0F12" stroke-width="2"/></svg>
```
`ui/__init__.py` e `ui/views/__init__.py`: vazios.

- [ ] **Step 3: `ui/theme.py`**

```python
"""Tokens visuais e componentes base. Tema escuro, um destaque (vermelho Poké Ball)."""
from __future__ import annotations

import flet as ft

BG, SIDEBAR, CARD, FIELD, HOVER = "#0E0F12", "#14161A", "#16181D", "#1A1D22", "#1F2329"
BORDER, TEXT, MUTED, FAINT = "#23252B", "#E8E9EC", "#9AA0AA", "#6B717B"
ACCENT, GREEN, AMBER = "#E8445A", "#3DD68C", "#F5A524"
RADIUS, RADIUS_SMALL, GAP, SIDEBAR_WIDTH, CONTROL_HEIGHT = 12, 8, 12, 220, 36

BOARD_TITLES = {"ready": "Placa pronta", "checking": "Procurando a placa", "none": "Sem placa",
                "many": "Várias placas", "busy": "Placa ocupada", "silent": "Placa sem resposta",
                "flashing": "Gravando firmware"}
BOARD_COLORS = {"ready": GREEN, "checking": AMBER, "flashing": AMBER}


def text(value: str, size: int = 13, color: str = TEXT, bold: bool = False, **kw) -> ft.Text:
    return ft.Text(value, size=size, color=color, weight=ft.FontWeight.W_600 if bold else None, **kw)


def muted(value: str, size: int = 12, **kw) -> ft.Text:
    return text(value, size=size, color=MUTED, **kw)


def icon(name: str, size: int = 18, color: str = MUTED) -> ft.Image:
    return ft.Image(src=f"icons/{name}.svg", width=size, height=size, color=color,
                    color_blend_mode=ft.BlendMode.SRC_IN)


def border(color: str = BORDER, width: int = 1) -> ft.Border:
    side = ft.BorderSide(width, color)
    return ft.Border(top=side, right=side, bottom=side, left=side)


def card(content: ft.Control, padding: int = 14, on_click=None, selected: bool = False,
         **kw) -> ft.Container:
    return ft.Container(content=content, padding=padding, bgcolor=CARD, border_radius=RADIUS,
                        border=border(ACCENT if selected else BORDER), on_click=on_click,
                        ink=on_click is not None, **kw)


def button(label: str, on_click=None, primary: bool = True, icon_name: str | None = None,
           disabled: bool = False) -> ft.Button:
    ink = "#FFFFFF" if primary else TEXT
    style = ft.ButtonStyle(
        bgcolor={ft.ControlState.DISABLED: HOVER, ft.ControlState.DEFAULT: ACCENT if primary else HOVER},
        color={ft.ControlState.DISABLED: FAINT, ft.ControlState.DEFAULT: ink},
        shape=ft.StadiumBorder(), padding=ft.Padding(18, 8, 18, 8), elevation=0,
        text_style=ft.TextStyle(size=13, weight=ft.FontWeight.W_600))
    return ft.Button(label, icon=icon(icon_name, 16, ink) if icon_name else None,
                     on_click=on_click, style=style, disabled=disabled, height=CONTROL_HEIGHT)


def dot(color: str) -> ft.Container:
    return ft.Container(width=8, height=8, border_radius=4, bgcolor=color)


def board_card(info) -> ft.Container:
    color = BOARD_COLORS.get(info.kind, ACCENT)
    bad = color == ACCENT
    return ft.Container(
        padding=10, border_radius=RADIUS_SMALL, bgcolor="#2A1519" if bad else CARD,
        border=border("#5A2630" if bad else BORDER),
        content=ft.Column([ft.Row([dot(color), text(BOARD_TITLES.get(info.kind, info.kind), 12, bold=True)],
                                  spacing=6),
                           muted(info.message, 11)], spacing=4))


def brand() -> ft.Row:
    return ft.Row([ft.Image(src="pokeball.svg", width=22, height=22),
                   text("Distribuidor", 15, bold=True)], spacing=8)


def nav_item(label: str, icon_name: str, selected: bool, on_click) -> ft.Container:
    color = TEXT if selected else MUTED
    return ft.Container(content=ft.Row([icon(icon_name, 16, color), text(label, 13, color)], spacing=10),
                        padding=ft.Padding(10, 8, 10, 8), border_radius=RADIUS_SMALL,
                        bgcolor=HOVER if selected else None, on_click=on_click, ink=True)


def crumbs(parts: list[tuple[str, object]]) -> ft.Row:
    """[(rótulo, on_click ou None)]; o último é a etapa atual."""
    items: list[ft.Control] = []
    for index, (label, on_click) in enumerate(parts):
        if index:
            items.append(muted("›", 12))
        last = index == len(parts) - 1
        items.append(ft.Container(text(label, 12, TEXT if last else MUTED, bold=last),
                                  on_click=None if last else on_click))
    return ft.Row(items, spacing=6)


def stat(label: str, value: str) -> ft.Container:
    return card(ft.Column([muted(label, 11), text(value, 20, bold=True)], spacing=2), padding=12, expand=True)


def apply_page(page: ft.Page) -> None:
    page.title = "Distribuidor de Eventos"
    page.bgcolor = BG
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(color_scheme=ft.ColorScheme(primary=ACCENT, surface=CARD))
    page.padding = 0
    page.window.width, page.window.height = 1180, 760
    page.window.min_width, page.window.min_height = 960, 620
```

- [ ] **Step 4: `ui/sprites.py`**

```python
"""Caixas de sprite: Poké Ball apagada até o sprite chegar (do cache ou baixado numa thread)."""
from __future__ import annotations

import flet as ft


class SpriteSlots:
    def __init__(self, shell, size: int):
        self.shell, self.size = shell, size
        self._slots: dict[int, list[ft.Container]] = {}

    def box(self, species: int) -> ft.Container:
        box = ft.Container(width=self.size, height=self.size, alignment=ft.Alignment.CENTER)
        path = self.shell.service.sprites.cached(species)
        box.content = self._image(path.read_bytes()) if path else self._placeholder()
        if path is None and species > 0:
            self._slots.setdefault(species, []).append(box)
        return box

    def _placeholder(self) -> ft.Control:
        return ft.Image(src="pokeball.svg", width=self.size // 3, height=self.size // 3, opacity=0.25)

    def _image(self, data: bytes) -> ft.Image:
        return ft.Image(src=data, width=self.size, height=self.size, filter_quality=ft.FilterQuality.NONE)

    def load(self) -> None:
        """Baixa numa thread os sprites que faltam e troca as caixas pela imagem."""
        pending, self._slots = self._slots, {}

        def work():
            for species, boxes in pending.items():
                path = self.shell.service.sprites.get(species)
                if path is None:
                    continue
                data = path.read_bytes()

                def apply(boxes=boxes, data=data):
                    for box in boxes:
                        box.content = self._image(data)
                        box.update()

                self.shell.ui(apply)

        self.shell.in_thread(work)
```
(Se o Flet 1.0.2 recusar `bytes` em `ft.Image(src=...)`, use `src_base64=base64.b64encode(data).decode()` e anote no commit.)

- [ ] **Step 5: `ui/views/placeholder.py`** (temporário; as Tasks 14 e 15 trocam pelas views reais)

```python
import flet as ft

from ui import theme as t


class Placeholder:
    def __init__(self, shell, title: str):
        self.control = ft.Column([t.text(title, 20, bold=True), t.muted("Em construção")])

    def show(self, snap) -> None:
        pass

    def update(self, snap) -> None:
        pass
```

- [ ] **Step 6: `ui/app.py`**

```python
"""A janela: barra lateral (abas + cartão da placa), faixa de atualização e a view da aba atual."""
from __future__ import annotations

import sys
import threading
import time
import traceback
from pathlib import Path

import flet as ft

from distrib import update
from distrib.config import load, resource_root
from distrib.service import Service, Snapshot
from ui import theme as t

ASSETS = resource_root() / "ui" / "assets"
NAV = (("distribuir", "Distribuir", "gamepad-2"), ("placa", "Placa", "cpu"),
       ("ajustes", "Ajustes", "settings"))


class Shell:
    def __init__(self, page: ft.Page, service: Service):
        from ui.views.placeholder import Placeholder
        self.page, self.service = page, service
        self.picker = ft.FilePicker()
        self.launcher = ft.UrlLauncher()
        self.views = {key: Placeholder(self, label) for key, label, _ in NAV}
        self.inicio = Placeholder(self, "Primeira abertura")
        self.current = "distribuir"
        self._shown = None
        self._pending = False
        self._pending_lock = threading.Lock()
        self.nav = ft.Column(spacing=4)
        self.board_card = ft.Container()
        self.update_bar = ft.Container(visible=False, bgcolor=t.CARD, padding=ft.Padding(24, 10, 24, 10),
                                       border=ft.Border(bottom=ft.BorderSide(1, t.BORDER)))
        self.body = ft.Container(expand=True, padding=24)
        sidebar = ft.Container(
            width=t.SIDEBAR_WIDTH, bgcolor=t.SIDEBAR, padding=ft.Padding(12, 16, 12, 16),
            border=ft.Border(right=ft.BorderSide(1, t.BORDER)),
            content=ft.Column([t.brand(), ft.Container(height=12), self.nav,
                               ft.Container(expand=True), self.board_card], spacing=0, expand=True))
        page.add(ft.Row([sidebar, ft.Column([self.update_bar, self.body], spacing=0, expand=True)],
                        spacing=0, expand=True))
        service.subscribe(self._on_snapshot)
        self.in_thread(self._ticker)

    # ---- infraestrutura ----
    def ui(self, fn) -> None:
        """Roda fn no laço da página: controles não podem ser mexidos de outra thread."""
        async def call():
            try:
                fn()
            except Exception:
                traceback.print_exc()
        self.page.run_task(call)

    def in_thread(self, fn, *args) -> None:
        threading.Thread(target=fn, args=args, daemon=True).start()

    def toast(self, message: str) -> None:
        self.ui(lambda: self.page.show_dialog(ft.SnackBar(ft.Text(message), duration=4000)))

    def _ticker(self) -> None:
        # O tempo "no ar" anda sem mudar o Snapshot: redesenha uma vez por segundo durante a distribuição.
        while True:
            time.sleep(1)
            if self.service.snapshot().run is not None:
                self._on_snapshot(self.service.snapshot())

    def _on_snapshot(self, snap: Snapshot) -> None:      # de qualquer thread
        with self._pending_lock:
            if self._pending:
                return
            self._pending = True
        self.ui(self._flush)

    def _flush(self) -> None:
        with self._pending_lock:
            self._pending = False
        self.render()

    # ---- navegação e desenho ----
    def navigate(self, key: str) -> None:
        self.current = key
        self.render()

    def _active_view(self, snap: Snapshot):
        if self.current == "distribuir" and not snap.ready and snap.run is None:
            return self.inicio
        return self.views[self.current]

    def render(self) -> None:
        snap = self.service.snapshot()
        self.nav.controls = [t.nav_item(label, icon, key == self.current,
                                        lambda e, k=key: self.navigate(k)) for key, label, icon in NAV]
        self.board_card.content = t.board_card(snap.board)
        self.update_bar.visible = snap.update_state in ("ready", "error")
        if self.update_bar.visible:
            self.update_bar.content = self._update_row(snap)
        view = self._active_view(snap)
        if view is not self._shown:
            self._shown = view
            self.body.content = view.control
            view.show(snap)
        else:
            view.update(snap)
        self.page.update()

    def _update_row(self, snap: Snapshot) -> ft.Row:
        if snap.update_state == "error":
            return ft.Row([t.icon("triangle-alert", 16, t.AMBER),
                           t.muted("A atualização falhou. Baixe a versão nova no GitHub e substitua o .exe.")])
        busy = snap.run is not None
        return ft.Row([t.icon("download", 16, t.GREEN),
                       t.text(f"Atualização {snap.update_version} pronta.", 13),
                       t.muted("Reinicie quando a distribuição terminar." if busy else ""),
                       ft.Container(expand=True),
                       t.button("Reiniciar", self._restart, disabled=busy)], spacing=10)

    def _restart(self, e=None) -> None:
        if self.service.apply_update():
            self.page.run_task(self.page.window.destroy)


def _log_crashes(cfg) -> None:
    crash = cfg.logs_dir / "erros.log"

    def write(kind, value, tb):
        with open(crash, "a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            traceback.print_exception(kind, value, tb, file=f)

    sys.excepthook = write
    threading.excepthook = lambda args: write(args.exc_type, args.exc_value, args.exc_traceback)


def run() -> None:
    cfg = load()
    for folder in (cfg.data_dir, cfg.logs_dir):
        folder.mkdir(parents=True, exist_ok=True)
    exe = Path(sys.executable) if getattr(sys, "frozen", False) else None
    if exe is not None:
        update.cleanup(exe)
    _log_crashes(cfg)
    service = Service(cfg, exe_path=exe)

    def main(page: ft.Page) -> None:
        t.apply_page(page)
        Shell(page, service)
        service.start_background(updates=exe is not None)

    try:
        ft.run(main, assets_dir=str(ASSETS))
    finally:
        service.shutdown()
```

- [ ] **Step 7: Abrir o app e conferir**

```bash
DISTRIB_DATA_DIR="$PWD/build/out/dados-dev" $PY main.py
```
Conferir na janela: fundo escuro, barra lateral com a Poké Ball e "Distribuidor", 3 abas clicáveis com ícones, cartão da placa no rodapé mudando sozinho (com a placa plugada: "Placa pronta"; sem: "Sem placa"), "Primeira abertura" na aba Distribuir. Feche a janela: o processo termina. Corrija qualquer erro de API do Flet 1.0.2 que aparecer no terminal (nomes de parâmetros), sem mudar o comportamento.

- [ ] **Step 8: Rodar os testes e commit**

```bash
$PY -m pytest -q 2>&1 | tail -3
git add build/fetch_icons.py ui
git commit -m "Interface: tema, ícones Lucide, Poké Ball e a janela com barra lateral"
```

---

### Task 14: Interface — aba Distribuir (jogo → grade → eventos → distribuindo)

**Files:**
- Create: `ui/views/distribuir.py`
- Modify: `ui/app.py` (usar a view real)

**Interfaces:**
- Consumes: `Shell` (Task 13), `Service.groups/event_count/start/pause/resume/stop/adapters/sprites`, `Snapshot.run/log`, `SpriteSlots`.
- Produces: `DistribuirView(shell)` com `control`, `show(snap)`, `update(snap)`.

- [ ] **Step 1: `ui/views/distribuir.py`**

```python
"""Distribuir: Jogo → grade de Pokémon → eventos do Pokémon → distribuindo.

Parar volta para a grade do jogo; Pausar fica na tela. Trocar de aba não interrompe nada.
"""
from __future__ import annotations

import threading
import time

import flet as ft

from distrib.catalog import Event, Group
from ui import theme as t
from ui.sprites import SpriteSlots

GAMES = (("swsh", "Sword / Shield", "Vários consoles ao mesmo tempo", 888, ("#2B3A67", "#4B2B67")),
         ("frlg", "FireRed / LeafGreen", "Um console por vez", 6, ("#6B2B2B", "#6B4A2B")))
TITLES = {game: title for game, title, *_ in GAMES}
RUN_STATES = {"starting": "Preparando…", "on_air": "No ar", "console": "Console conectado",
              "paused": "Pausado", "no_board": "Esperando a placa", "failed": "Falhou",
              "idle": "Parado"}
RESULTS = {"entregue": "Entregue", "equipe cheia": "Equipe cheia", "não entregue": "Não entregue"}


def elapsed(since: float | None) -> str:
    if since is None:
        return "—"
    seconds = int(time.monotonic() - since)
    return f"{seconds // 3600:d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"


class DistribuirView:
    def __init__(self, shell):
        self.shell, self.service = shell, shell.service
        self.game: str | None = None
        self.group: Group | None = None
        self.stopping = False
        self._step: str | None = None
        self._timer: threading.Timer | None = None
        self.control = ft.Column(expand=True, spacing=t.GAP)
        self.search = ft.TextField(hint_text="Buscar Pokémon…", on_change=self._on_search,
                                   bgcolor=t.FIELD, border_color=t.BORDER, border_radius=t.RADIUS_SMALL,
                                   text_size=13, height=40, content_padding=ft.Padding(12, 8, 12, 8))
        self.grid = ft.GridView(max_extent=160, child_aspect_ratio=0.78, spacing=10,
                                run_spacing=10, expand=True)
        self.run_title = t.text("", 18, bold=True)
        self.run_state = t.muted("")
        self.pause_slot = ft.Container()
        self.stop_slot = ft.Container()
        self.stats = ft.Row(spacing=10)
        self.log = ft.ListView(expand=True, spacing=2, auto_scroll=True)

    # ---- ciclo da view ----
    def step(self, snap) -> str:
        if snap.run is not None:
            return "distribuindo"
        if self.group is not None:
            return "eventos"
        return "grade" if self.game is not None else "jogos"

    def show(self, snap) -> None:
        self._step = None
        self.update(snap)

    def update(self, snap) -> None:
        if snap.run is None:
            self.stopping = False
        step = self.step(snap)
        if step != self._step:
            self._step = step
            self.control.controls = getattr(self, f"_build_{step}")(snap)
        if step == "distribuindo":
            self._update_run(snap)

    def _redraw(self) -> None:
        self._step = None
        self.shell.render()

    # ---- 1. jogos ----
    def _build_jogos(self, snap) -> list[ft.Control]:
        slots = SpriteSlots(self.shell, 96)
        cards = []
        for game, title, subtitle, mascot, colors in GAMES:
            header = ft.Container(
                content=slots.box(mascot), height=150, border_radius=t.RADIUS_SMALL,
                alignment=ft.Alignment.CENTER,
                gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                           colors=list(colors)))
            body = ft.Column([header, t.text(title, 16, bold=True),
                              t.muted(f"{self.service.event_count(game)} eventos · {subtitle}")], spacing=8)
            cards.append(t.card(body, padding=16, expand=True,
                                on_click=lambda e, g=game: self._pick_game(g)))
        slots.load()
        return [t.crumbs([("Distribuir", None)]), ft.Row(cards, spacing=t.GAP)]

    def _pick_game(self, game: str) -> None:
        self.game, self.group = game, None
        self.search.value = ""
        self._redraw()

    def _to_games(self, e=None) -> None:
        self.game = self.group = None
        self._redraw()

    # ---- 2. grade ----
    def _build_grade(self, snap) -> list[ft.Control]:
        self._fill_grid()
        return [t.crumbs([("Distribuir", self._to_games), (TITLES[self.game], None)]),
                self.search, self.grid]

    def _fill_grid(self) -> None:
        slots = SpriteSlots(self.shell, 96)
        self.grid.controls = [self._tile(group, slots)
                              for group in self.service.groups(self.game, self.search.value or "")]
        slots.load()

    def _tile(self, group: Group, slots: SpriteSlots) -> ft.Container:
        n = len(group.events)
        center = ft.CrossAxisAlignment.CENTER
        body = ft.Column([
            slots.box(group.species) if group.species else ft.Container(
                t.icon("package" if group.key == "item" else "zap", 40, t.MUTED),
                width=96, height=96, alignment=ft.Alignment.CENTER),
            t.text(group.name, 13, bold=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            t.muted(f"{n} evento{'s' if n > 1 else ''}", 11),
            t.muted(" · ".join(group.highlights), 11, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
        ], horizontal_alignment=center, spacing=4)
        return t.card(body, padding=10, on_click=lambda e, g=group: self._pick_group(g))

    def _on_search(self, e) -> None:
        if self._timer is not None:
            self._timer.cancel()

        def refresh():
            self._fill_grid()
            self.grid.update()

        self._timer = threading.Timer(0.25, lambda: self.shell.ui(refresh))
        self._timer.start()

    def _pick_group(self, group: Group) -> None:
        self.group = group
        self._redraw()

    def _to_grid(self, e=None) -> None:
        self.group = None
        self._redraw()

    # ---- 3. eventos do Pokémon ----
    def _build_eventos(self, snap) -> list[ft.Control]:
        group = self.group
        slots = SpriteSlots(self.shell, 192)
        n = len(group.events)
        header = ft.Row([slots.box(group.species) if group.species else ft.Container(width=8),
                         ft.Column([t.text(group.name, 22, bold=True),
                                    t.muted(f"{n} evento{'s' if n > 1 else ''} disponíve{'is' if n > 1 else 'l'}")],
                                   spacing=4)], spacing=16)
        rows = [self._event_row(event, first=index == 0) for index, event in enumerate(group.events)]
        slots.load()
        return [t.crumbs([("Distribuir", self._to_games), (TITLES[self.game], self._to_grid),
                          (group.name, None)]),
                header, ft.ListView(rows, spacing=8, expand=True)]

    def _event_row(self, event: Event, first: bool) -> ft.Container:
        ot = dict(event.details).get("OT", "")
        line = " · ".join(p for p in (event.region, *event.highlights, f"OT {ot}" if ot else "") if p)
        return t.card(ft.Row([ft.Column([t.text(event.name, 13, bold=True), t.muted(line, 11)],
                                        spacing=2, expand=True),
                              t.button("Distribuir", lambda e, ev=event: self._start(ev), primary=first,
                                       icon_name="play")]), padding=12)

    def _start(self, event: Event) -> None:
        game = self.game

        def work():
            try:
                self.service.start(game, event)
            except RuntimeError as exc:
                self.shell.toast(f"Não deu para começar: {exc}")

        self.shell.in_thread(work)

    # ---- 4. distribuindo ----
    def _build_distribuindo(self, snap) -> list[ft.Control]:
        run = snap.run
        self.game = run.game
        slots = SpriteSlots(self.shell, 96)
        header = ft.Row([slots.box(run.event.species),
                         ft.Column([self.run_title, self.run_state], spacing=2, expand=True),
                         self.pause_slot, self.stop_slot], spacing=14)
        slots.load()
        name = self.group.name if self.group is not None else TITLES[run.game]
        return [t.crumbs([("Distribuir", None), (TITLES[run.game], None), (name, None),
                          (run.event.name, None)]),
                header, self.stats,
                t.muted(self.service.adapters[run.game].instructions, 12),
                t.card(self.log, padding=12, expand=True)]

    def _update_run(self, snap) -> None:
        run = snap.run
        self.run_title.value = run.event.name
        state = "Parando…" if self.stopping else RUN_STATES.get(run.state, run.state)
        if run.state == "failed" and run.detail:
            state += f" · {run.detail}"
        self.run_state.value = state
        paused = run.state == "paused"
        self.pause_slot.content = t.button("Continuar" if paused else "Pausar",
                                           self._resume if paused else self._pause, primary=False,
                                           icon_name="play" if paused else "pause",
                                           disabled=self.stopping)
        self.stop_slot.content = t.button("Parar", self._stop, icon_name="square", disabled=self.stopping)
        if self.service.adapters[run.game].mode == "broadcast":
            self.stats.controls = [t.stat("No ar há", elapsed(run.since)),
                                   t.stat("Canal", str(run.channel or "—"))]
        else:
            self.stats.controls = [t.stat("Entregues", str(run.deliveries)),
                                   t.stat("Último resultado", RESULTS.get(run.last_event, "—")),
                                   t.stat("No ar há", elapsed(run.since)),
                                   t.stat("Console", "conectado" if run.state == "console" else "—")]
        self.log.controls = [ft.Text(line, size=11, font_family="Consolas", color=t.MUTED, selectable=True)
                             for line in snap.log[-200:]]

    def _pause(self, e=None) -> None:
        self.shell.in_thread(self.service.pause)

    def _resume(self, e=None) -> None:
        self.shell.in_thread(self.service.resume)

    def _stop(self, e=None) -> None:
        run = self.service.snapshot().run
        if run is None:
            return
        self.stopping = True
        self.game, self.group = run.game, None        # ao parar, volta para a grade do jogo
        self.shell.in_thread(self.service.stop)
        self.shell.render()
```

- [ ] **Step 2: Ligar a view em `ui/app.py`**

No `Shell.__init__`, troque a linha `self.views = {key: Placeholder(self, label) for key, label, _ in NAV}` por:

```python
        from ui.views.distribuir import DistribuirView
        self.views = {key: Placeholder(self, label) for key, label, _ in NAV}
        self.views["distribuir"] = DistribuirView(self)
```

- [ ] **Step 3: Conferir no app (com catálogo e chaves de verdade)**

```bash
export DISTRIB_DATA_DIR="$LOCALAPPDATA/Distribuidor"
$PY -m distrib atualizar-catalogo
$PY main.py
```
Conferir: (1) dois cartões de jogo com contagem e sprite; (2) grade com sprites aparecendo aos poucos, busca "zarude" filtra, acentos ignorados, quadradinhos "Itens" e "Presentes do pokeldn" no fim; (3) clicar no Zarude lista os eventos com região/destaques e "Distribuir"; (4) com a placa plugada, "Distribuir" no Jungle Zarude mostra "Preparando…" → "No ar", canal e tempo andando, log ao vivo, e o Sword recebe o cartão; (5) "Pausar" fica na tela e vira "Continuar"; (6) "Parar" mostra "Parando…" e volta para a grade do Sword/Shield; (7) tirar o USB no meio: cartão lateral vermelho "Placa desconectada… continua quando ela voltar"; replugar: volta a "No ar".

- [ ] **Step 4: Commit**

```bash
git add ui/views/distribuir.py ui/app.py
git commit -m "Interface: aba Distribuir (jogo, grade por Pokémon, eventos, distribuindo)"
```

---

### Task 15: Interface — primeira abertura, Placa e Ajustes

**Files:**
- Create: `ui/views/inicio.py`, `ui/views/placa.py`, `ui/views/ajustes.py`
- Modify: `ui/app.py`
- Delete: `ui/views/placeholder.py`

**Interfaces:**
- Consumes: `Shell.picker/launcher/toast/in_thread/navigate/ui`, `Service.set_keys/download_catalog/check_board/flash_board/check_update/cfg`, `radio.DRIVERS`, `__version__`.
- Produces: `InicioView`, `PlacaView`, `AjustesView` (mesmo protocolo `control/show/update`).

- [ ] **Step 1: `ui/views/inicio.py`**

```python
"""Primeira abertura: prod.keys, eventos e placa. Cada passo fica verde quando pronto."""
from __future__ import annotations

from pathlib import Path

import flet as ft

from ui import theme as t


async def choose_keys(shell) -> None:
    files = await shell.picker.pick_files(allowed_extensions=["keys"],
                                          file_type=ft.FilePickerFileType.CUSTOM)
    if not files:
        return
    try:
        shell.service.set_keys(Path(files[0].path))
        shell.toast("prod.keys guardado.")
    except (ValueError, OSError) as exc:
        shell.toast(str(exc))


def download_events(shell, on_line) -> None:
    def work():
        try:
            shell.service.download_catalog(on_line)
        except OSError as exc:
            on_line(f"Falhou: {exc}. Confira a internet e tente de novo.")
    shell.in_thread(work)


class InicioView:
    def __init__(self, shell):
        self.shell = shell
        self.downloading = False
        self.progress_text = t.muted("", 11)
        self.steps = ft.Column(spacing=10)
        self.control = ft.Column([t.text("Vamos preparar o Distribuidor", 22, bold=True),
                                  t.muted("Três passos. Você só faz isso uma vez."),
                                  ft.Container(height=8), self.steps], spacing=6)

    def show(self, snap) -> None:
        self.update(snap)

    def update(self, snap) -> None:
        if snap.catalog_ok:
            self.downloading = False
        self.steps.controls = [
            self._step(1, "Suas chaves do Switch (prod.keys)", snap.keys_ok,
                       "Guardado." if snap.keys_ok else "Escolha o prod.keys extraído do seu próprio console.",
                       t.button("Escolher prod.keys", self._keys, icon_name="key-round",
                                primary=not snap.keys_ok)),
            self._step(2, "Eventos do Events Gallery", snap.catalog_ok,
                       "Baixados." if snap.catalog_ok else "Cerca de 56 MB, uma vez só.",
                       t.button("Baixando…" if self.downloading else "Baixar eventos", self._download,
                                icon_name="download", disabled=self.downloading or snap.catalog_ok),
                       extra=ft.Column([ft.ProgressBar(color=t.ACCENT, bgcolor=t.FIELD),
                                        self.progress_text], spacing=4) if self.downloading else None),
            self._step(3, "Placa conectada", snap.board.ok, snap.board.message,
                       t.button("Abrir a aba Placa", lambda e: self.shell.navigate("placa"),
                                icon_name="usb", primary=False)),
        ]

    def _step(self, number, title, done, detail, action, extra=None) -> ft.Container:
        badge = ft.Container(t.icon("check", 14, "#FFFFFF") if done else t.text(str(number), 12, bold=True),
                             width=26, height=26, border_radius=13, alignment=ft.Alignment.CENTER,
                             bgcolor=t.GREEN if done else t.HOVER)
        column = ft.Column([t.text(title, 14, bold=True), t.muted(detail, 12)], spacing=2, expand=True)
        if extra is not None:
            column.controls.append(extra)
        return t.card(ft.Row([badge, column, action], spacing=14), padding=14)

    async def _keys(self, e) -> None:
        await choose_keys(self.shell)

    def _download(self, e) -> None:
        self.downloading = True

        def line(text):
            self.shell.ui(lambda: (setattr(self.progress_text, "value", text), self.shell.render()))

        download_events(self.shell, line)
        self.shell.render()
```

- [ ] **Step 2: `ui/views/placa.py`**

```python
"""Placa: estado, porta, ponte USB, "Preparar placa" (grava o firmware) e drivers."""
from __future__ import annotations

import flet as ft

from distrib import radio
from ui import theme as t


class PlacaView:
    def __init__(self, shell):
        self.shell, self.service = shell, shell.service
        self.control = ft.Column(expand=True, spacing=t.GAP)

    def show(self, snap) -> None:
        self.update(snap)

    def update(self, snap) -> None:
        board, flashing = snap.board, snap.flash_progress is not None
        can_flash = snap.run is None and not flashing and board.kind not in ("none", "many")
        info = t.card(ft.Column([
            ft.Row([t.dot(t.GREEN if board.ok else t.ACCENT), t.text(t.BOARD_TITLES.get(board.kind, board.kind), 15, bold=True)],
                   spacing=8),
            t.muted(board.message),
            ft.Row([t.muted(f"Porta: {board.port or '—'}"), t.muted(f"Ponte USB: {board.bridge or '—'}")], spacing=24),
            ft.Row([t.button("Preparar placa", self._ask_flash, icon_name="zap", disabled=not can_flash),
                    t.button("Testar de novo", self._recheck, primary=False, icon_name="refresh-cw",
                             disabled=flashing or snap.run is not None)], spacing=10),
            t.muted("Preparar placa grava o firmware do pokeldn. Faça isso numa placa nova ou se ela "
                    "parar de responder.", 11),
        ], spacing=10))
        controls = [t.text("Placa", 22, bold=True), info]
        if flashing:
            controls.append(t.card(ft.Column([
                ft.ProgressBar(value=snap.flash_progress, color=t.ACCENT, bgcolor=t.FIELD),
                ft.ListView([ft.Text(line, size=11, font_family="Consolas", color=t.MUTED)
                             for line in snap.log[-60:]], height=180, auto_scroll=True)], spacing=8)))
        if board.kind == "none":
            controls.append(self._drivers())
        self.control.controls = controls

    def _drivers(self) -> ft.Container:
        links = [t.button(name, lambda e, url=url: self._open(url), primary=False, icon_name="external-link")
                 for name, url in radio.DRIVERS.items()]
        return t.card(ft.Column([
            t.text("A placa está plugada e não aparece?", 14, bold=True),
            t.muted("Instale o driver do chip USB da sua placa (vem escrito perto do conector: "
                    "CP2102, CH340 ou CH9102) e replugue o cabo. Use um cabo de dados, não só de carga."),
            ft.Row(links, spacing=8, wrap=True)], spacing=8))

    def _open(self, url: str) -> None:
        self.shell.page.run_task(self.shell.launcher.launch_url, url)

    def _recheck(self, e=None) -> None:
        self.shell.in_thread(self.service.check_board, True)

    def _ask_flash(self, e=None) -> None:
        def close(e=None):
            self.shell.page.pop_dialog()

        def confirm(e=None):
            close()
            self.shell.in_thread(self._flash)

        self.shell.page.show_dialog(ft.AlertDialog(
            modal=True, bgcolor=t.CARD,
            title=t.text("Preparar a placa?", 16, bold=True),
            content=t.muted("O firmware do pokeldn será gravado e o que estiver na placa será apagado. "
                            "Não desplugue o cabo até terminar (cerca de 30 segundos)."),
            actions=[t.button("Cancelar", close, primary=False), t.button("Gravar", confirm, icon_name="zap")]))

    def _flash(self) -> None:
        try:
            code = self.service.flash_board()
        except RuntimeError as exc:
            self.shell.toast(str(exc))
            return
        self.shell.toast("Placa preparada." if code == 0 else
                         "A gravação falhou. Veja o log, replugue a placa e tente de novo.")
```
(Se `page.pop_dialog` não existir no Flet 1.0.2, feche com `dialog.open = False; page.update()` guardando o diálogo numa variável; anote no commit.)

- [ ] **Step 3: `ui/views/ajustes.py`**

```python
"""Ajustes: prod.keys, eventos, versão/atualização, logs e créditos."""
from __future__ import annotations

import os

import flet as ft

from distrib import __version__
from ui import theme as t
from ui.views.inicio import choose_keys, download_events

CREDITS = (
    ("pokeldn (AGPL-3.0), de Decryptu: o rádio e os hosts. Código-fonte:", "https://github.com/Decryptu/pokeldn"),
    ("Events Gallery, do Project Pokémon: os arquivos dos eventos.", "https://github.com/projectpokemon/EventsGallery"),
    ("Sprites e nomes: PokeAPI.", "https://github.com/PokeAPI/sprites"),
    ("Ícones: Lucide (ISC).", "https://lucide.dev"),
    ("Distribuidor (MIT):", "https://github.com/Carlos-Gabryel/pokeldn-distrib"),
)
UPDATE_TEXT = {"none": "Você está na versão mais recente que encontramos.",
               "downloading": "Baixando a versão nova…", "ready": "Versão nova pronta: use “Reiniciar” no topo.",
               "error": "A última tentativa de atualizar falhou."}


class AjustesView:
    def __init__(self, shell):
        self.shell, self.service = shell, shell.service
        self.download_line = ""
        self.control = ft.Column(expand=True, spacing=t.GAP, scroll=ft.ScrollMode.AUTO)

    def show(self, snap) -> None:
        self.update(snap)

    def update(self, snap) -> None:
        idle = snap.run is None
        rows = [
            self._row("Chaves do Switch", "prod.keys guardado." if snap.keys_ok else "Nenhum prod.keys.",
                      t.button("Trocar prod.keys", self._keys, primary=False, icon_name="key-round")),
            self._row("Eventos", f"{self.service.event_count('swsh')} de Sword/Shield, "
                                 f"{self.service.event_count('frlg')} de FireRed/LeafGreen. {self.download_line}",
                      t.button("Baixar de novo", self._download, primary=False, icon_name="download",
                               disabled=not idle)),
            self._row(f"Versão {__version__}", UPDATE_TEXT.get(snap.update_state, ""),
                      t.button("Procurar atualização", self._check, primary=False, icon_name="refresh-cw")),
            self._row("Logs", str(self.service.cfg.logs_dir),
                      t.button("Abrir pasta", self._logs, primary=False, icon_name="folder-open")),
        ]
        credits = t.card(ft.Column([t.text("Créditos e licenças", 14, bold=True)] + [
            ft.Row([t.muted(label, 12), ft.Container(t.text(url, 12, t.ACCENT), on_click=lambda e, u=url: self._open(u))],
                   spacing=6, wrap=True) for label, url in CREDITS], spacing=6))
        self.control.controls = [t.text("Ajustes", 22, bold=True), *rows, credits]

    def _row(self, title: str, detail: str, action: ft.Control) -> ft.Container:
        return t.card(ft.Row([ft.Column([t.text(title, 14, bold=True), t.muted(detail, 12)], spacing=2, expand=True),
                              action], spacing=12))

    async def _keys(self, e) -> None:
        await choose_keys(self.shell)

    def _download(self, e) -> None:
        def line(text):
            self.download_line = text
            self.shell.ui(self.shell.render)
        download_events(self.shell, line)

    def _check(self, e) -> None:
        self.shell.toast("Procurando atualização…")
        self.shell.in_thread(self.service.check_update)

    def _logs(self, e) -> None:
        self.service.cfg.logs_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self.service.cfg.logs_dir)

    def _open(self, url: str) -> None:
        self.shell.page.run_task(self.shell.launcher.launch_url, url)
```

- [ ] **Step 4: Ligar as views em `ui/app.py`**

No `Shell.__init__`, troque o bloco de views por:

```python
        from ui.views.ajustes import AjustesView
        from ui.views.distribuir import DistribuirView
        from ui.views.inicio import InicioView
        from ui.views.placa import PlacaView
        self.views = {"distribuir": DistribuirView(self), "placa": PlacaView(self), "ajustes": AjustesView(self)}
        self.inicio = InicioView(self)
```
Apague `from ui.views.placeholder import Placeholder` e o arquivo: `git rm -q ui/views/placeholder.py`.

- [ ] **Step 5: Conferir no app com uma pasta de dados vazia**

```bash
DISTRIB_DATA_DIR="$PWD/build/out/dados-novos" $PY main.py
```
Conferir: os 3 passos aparecem; escolher um arquivo qualquer `.keys` inválido mostra o motivo; escolher o `prod.keys` real deixa o passo 1 verde; "Baixar eventos" mostra barra e linhas e termina verde; com a placa plugada, o passo 3 fica verde e a aba Distribuir passa a mostrar os jogos. Aba Placa: "Testar de novo" funciona; sem placa aparecem os 3 links de driver. Aba Ajustes: contagens, "Abrir pasta" abre o Explorer, links abrem o navegador.

- [ ] **Step 6: Commit**

```bash
git add -A ui
git commit -m "Interface: primeira abertura, aba Placa (Preparar placa) e Ajustes"
```

---

### Task 16: Empacotamento (`Distribuidor.exe`)

**Files:**
- Create: `build/fetch_firmware.py`, `build/make_icon.py`, `build/pack.py`, `ui/assets/icon.ico` (gerado)

**Interfaces:**
- Consumes: `board.FIRMWARE`, `distrib.__version__`.
- Produces: `dist/Distribuidor.exe`; `firmware/*.bin` (não versionado).

- [ ] **Step 1: `build/fetch_firmware.py`**

```python
"""Baixa os 4 firmwares do Release v0.5.0 do pokeldn para firmware/, conferindo o SHA-256."""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from distrib.board import FIRMWARE  # noqa: E402

TAG = "v0.5.0"
API = f"https://api.github.com/repos/Decryptu/pokeldn/releases/tags/{TAG}"
OUT = Path(__file__).resolve().parent.parent / "firmware"
HEADERS = {"User-Agent": "Distribuidor-build"}


def main() -> None:
    with urllib.request.urlopen(urllib.request.Request(API, headers=HEADERS), timeout=30) as resp:
        assets = {a["name"]: a for a in json.loads(resp.read())["assets"]}
    OUT.mkdir(exist_ok=True)
    for name in FIRMWARE.values():
        asset = assets[name]
        with urllib.request.urlopen(urllib.request.Request(asset["browser_download_url"], headers=HEADERS),
                                    timeout=120) as resp:
            data = resp.read()
        digest = (asset.get("digest") or "").removeprefix("sha256:")
        if digest and hashlib.sha256(data).hexdigest() != digest:
            raise SystemExit(f"{name}: SHA-256 não confere")
        (OUT / name).write_bytes(data)
        print(f"{name}: {len(data)} bytes")


if __name__ == "__main__":
    main()
```
Run: `$PY build/fetch_firmware.py` → 4 linhas com tamanhos.

- [ ] **Step 2: `build/make_icon.py`** (desenha a Poké Ball do app com Pillow)

```python
"""Gera ui/assets/icon.ico (Poké Ball) para o .exe."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "ui" / "assets" / "icon.ico"


def main() -> None:
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    box = (8, 8, size - 8, size - 8)
    d.ellipse(box, fill="#F4F5F7")
    d.pieslice(box, 180, 360, fill="#E8445A")
    d.rectangle((8, size // 2 - 10, size - 8, size // 2 + 10), fill="#0E0F12")
    r = 40
    c = size // 2
    d.ellipse((c - r, c - r, c + r, c + r), fill="#0E0F12")
    d.ellipse((c - r + 16, c - r + 16, c + r - 16, c + r - 16), fill="#F4F5F7")
    img.save(OUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(OUT)


if __name__ == "__main__":
    main()
```
Run: `$PY build/make_icon.py`.

- [ ] **Step 3: `build/pack.py`**

```python
"""Gera dist/Distribuidor.exe com o flet pack (PyInstaller): app + pokeldn v0.5.0 + firmwares."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from distrib import __version__  # noqa: E402
from distrib.board import FIRMWARE  # noqa: E402

POKELDN = ROOT / "vendor" / "pokeldn"
FLET = "import sys; from flet_cli.cli import main; sys.argv[0] = 'flet'; main()"


def main() -> int:
    missing = [n for n in FIRMWARE.values() if not (ROOT / "firmware" / n).is_file()]
    if missing:
        raise SystemExit(f"Faltam firmwares ({', '.join(missing)}): rode build/fetch_firmware.py")
    data = [(POKELDN / "bin", "vendor/pokeldn/bin"),
            (POKELDN / "pokeldn", "vendor/pokeldn/pokeldn"),
            (POKELDN / "vendor" / "LDN" / "ldn", "vendor/pokeldn/vendor/LDN/ldn"),
            (POKELDN / "config", "vendor/pokeldn/config"),
            (POKELDN / "LICENSE", "vendor/pokeldn"),
            (ROOT / "firmware", "firmware"),
            (ROOT / "ui" / "assets", "ui/assets"),
            (ROOT / "LICENSE", ".")]
    build_args = ["--console", "--hide-console=hide-early",
                  f"--paths={ROOT}", f"--paths={POKELDN}", f"--paths={POKELDN / 'bin'}",
                  f"--paths={POKELDN / 'vendor' / 'LDN'}",
                  "--hidden-import=swsh_gift_host", "--hidden-import=frlg_mg_host",
                  "--collect-submodules=pokeldn", "--collect-submodules=ldn",
                  "--collect-submodules=distrib", "--collect-submodules=ui",
                  "--collect-all=esptool", "--collect-all=esp_pylib",
                  "--exclude-module=pytest", "--exclude-module=textual"]
    args = [sys.executable, "-c", FLET, "pack", str(ROOT / "main.py"), "--name", "Distribuidor", "-y",
            "--distpath", str(ROOT / "dist"), "--icon", str(ROOT / "ui" / "assets" / "icon.ico"),
            "--product-name", "Distribuidor de Eventos", "--product-version", __version__,
            "--file-version", f"{__version__}.0", "--add-data",
            *[f"{src}{os.pathsep}{dest}" for src, dest in data],
            *[f"--pyinstaller-build-args={arg}" for arg in build_args]]
    code = subprocess.run(args, cwd=ROOT).returncode
    exe = ROOT / "dist" / "Distribuidor.exe"
    if code == 0 and not exe.exists():
        raise SystemExit("O flet pack terminou sem gerar dist/Distribuidor.exe")
    return code


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Gerar e testar o `.exe`**

```bash
$PY build/pack.py 2>&1 | tail -5
ls -la dist/Distribuidor.exe
dist/Distribuidor.exe --run bin/swsh_gift_host.py --help | head -3
dist/Distribuidor.exe --module distrib.runners.hello COM5
```
Expected: o `.exe` existe; o `--help` imprime o uso do host; com a placa plugada (troque `COM5` pela porta real), o HELLO imprime o texto do firmware. Depois abra `dist/Distribuidor.exe` com dois cliques: a janela abre com ícone de Poké Ball, sem console preto. Se faltar módulo no `.exe` (`ModuleNotFoundError` no `--run`), acrescente `--hidden-import`/`--collect-submodules` do pacote citado em `build_args` e gere de novo.

- [ ] **Step 5: Commit**

```bash
git add build/fetch_firmware.py build/make_icon.py build/pack.py ui/assets/icon.ico
git commit -m "Empacotamento: Distribuidor.exe com pokeldn v0.5.0, firmwares e ícone"
```

---

### Task 17: Limpeza do WSL e documentação

**Files:**
- Delete: `instalar.ps1`, `Iniciar Distribuicao.bat`, `windows/` (inteira), `tests/test_config_valor.py`, `docs/instalacao.md`
- Modify: `README.md`, `docs/testes-reais.md`

- [ ] **Step 1: Apagar o que era do WSL**

```bash
git rm -rq instalar.ps1 "Iniciar Distribuicao.bat" windows tests/test_config_valor.py docs/instalacao.md
grep -rn -i "wsl\|usbipd\|/dev/tty\|sudo\|root" --include=*.py --include=*.md distrib ui main.py build README.md docs/testes-reais.md | grep -v "docs/superpowers"
```
Expected: o grep não acha nada (ou só menções históricas que você então remove do README/testes).

- [ ] **Step 2: `README.md` (substituir)**

```markdown
# Distribuidor de Eventos

Distribui eventos de **Mystery Gift** para **Pokémon Sword/Shield** e **FireRed/LeafGreen** num
Switch, usando uma placa **ESP32** como rádio (via [pokeldn](https://github.com/Decryptu/pokeldn)).
Um programa só para Windows 10/11: sem WSL, sem instalação.

## Como usar

1. Baixe o `Distribuidor.exe` da [última versão](https://github.com/Carlos-Gabryel/pokeldn-distrib/releases/latest).
2. Abra. Se o Windows mostrar "O Windows protegeu o computador", clique em **Mais informações →
   Executar assim mesmo** (o programa não é assinado).
3. Na primeira abertura: escolha o seu `prod.keys` (extraído do seu próprio Switch), baixe os
   eventos e plugue a placa. Placa nova ou que não responde: aba **Placa → Preparar placa**.
4. **Distribuir → escolha o jogo → o Pokémon → o evento.** No console:
   - Sword/Shield: Presente Misterioso → Receber presente → Por comunicação local (vários consoles juntos).
   - FireRed/LeafGreen: MYSTERY GIFT → WONDER CARDS → FRIEND (um console por vez).

O programa se atualiza sozinho. Seus dados ficam em `%LOCALAPPDATA%\Distribuidor`.

## Desenvolvimento

```bash
git clone --recurse-submodules https://github.com/Carlos-Gabryel/pokeldn-distrib
py -3.14 -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe main.py
.venv/Scripts/python.exe build/fetch_firmware.py && .venv/Scripts/python.exe build/pack.py
```

## Licença e créditos

O código deste repositório é [MIT](LICENSE). O `.exe` inclui o
[pokeldn](https://github.com/Decryptu/pokeldn) e os firmwares dele, sob a licença do autor
(AGPL-3.0), sem modificação. Eventos: [Events Gallery](https://github.com/projectpokemon/EventsGallery),
do Project Pokémon. Sprites e nomes: [PokeAPI](https://pokeapi.co). Ícones: [Lucide](https://lucide.dev) (ISC).
```

- [ ] **Step 3: `docs/testes-reais.md`** — troque cada passo que cite WSL, `wsl -u root`, usbipd ou `/dev/ttyACM0` pelo equivalente no `.exe` (abrir o `Distribuidor.exe`; porta `COMx`; "aba Placa"). Acrescente ao fim:

```markdown
9. **Preparar placa:** apague a placa (`esptool --port COMx erase-flash`), abra o app, aba Placa →
   Preparar placa → Gravar. Esperado: barra até 100%, "Placa preparada.", cartão lateral verde.
10. **Atualização:** com a v2.0.0 aberta e um Release v2.0.1 publicado, o app mostra "Atualização
    v2.0.1 pronta", "Reiniciar" abre a v2.0.1 e o `Distribuidor.exe.old` some na abertura seguinte.
```

- [ ] **Step 4: Rodar e commit**

```bash
$PY -m pytest -q 2>&1 | tail -3
git add -A
git commit -m "Remove o caminho WSL (instalador, atalho, scripts) e documenta o .exe"
```
Expected: suíte toda verde.

---

### Task 18: Aceite real, Release e merge (manual: Opus + dono)

- [ ] **Step 1:** `$PY build/fetch_firmware.py && $PY build/pack.py`; copiar `dist/Distribuidor.exe` para o notebook (sem Python instalado; a placa liberada do WSL como na Task 2, Step 1).
- [ ] **Step 2:** Rodar `docs/testes-reais.md` inteiro (1–10) com o `.exe`, anotando o resultado de cada teste no próprio arquivo, com data.
- [ ] **Step 3:** Revisão final do branch inteiro (superpowers:requesting-code-review) e correções.
- [ ] **Step 4 (com aprovação do dono):** merge e Release.

```bash
git checkout master && git merge --no-ff exe-flet -m "Distribuidor como .exe nativo do Windows (Flet)"
git push origin master
gh release create v2.0.0 dist/Distribuidor.exe --repo Carlos-Gabryel/pokeldn-distrib --title "Distribuidor 2.0.0" --notes "Programa nativo do Windows: baixe o Distribuidor.exe e abra. Sem WSL."
gh release view v2.0.0 --repo Carlos-Gabryel/pokeldn-distrib --json assets -q '.assets[].digest'
```
Expected: o último comando mostra `sha256:...` (é o que a atualização automática confere).
- [ ] **Step 5:** Teste 10 (atualização): subir `__version__` para `2.0.1`, gerar, publicar `v2.0.1` e confirmar que a v2.0.0 se atualiza sozinha.

---

## Emendas da Task 2 (2026-10-03, placa real)

Resultado: SwSh nativo no Windows **ok** (Jungle Zarude recebido no Sword). FRLG nativo **pendente** (Task 2, Step 4).

1. **PKHeX obrigatório.** O `swsh_gift_host.py` do v0.5.0 valida todo cartão com o serviço .NET `services/pkhex`. No desenvolvimento: `dotnet publish vendor/pokeldn/services/pkhex -c Release -r win-x64 -o vendor/pokeldn/services/pkhex/dist -warnaserror` (o .NET SDK 10 já está instalado; a saída é ignorada pelo git do pokeldn). Task 16: rodar esse passo no `build/pack.py` e incluir `(POKELDN/"services"/"pkhex"/"dist", "vendor/pokeldn/services/pkhex/dist")` no `--add-data`. O `.exe` gerado é autônomo, então quem usa o app não precisa de .NET.
2. **Firmware precisa ser o v0.5.0** (o host novo usa `CMD_BAUD 0x02`). O `firmware/pokeldn-radio.bin` do Release foi gravado na placa do dono.
3. **Aquietar a placa antes de cada host (novo: `distrib/runners/quiet.py`, entra na Task 8).**
   - Depois de uma sessão, a placa fica em **921600** (o host não volta).
   - Parada em 115200, a placa repassa frames LDN do ar e a fila passa dos 5 s do HELLO do `open_serial`.
   - Solução provada em duas sessões seguidas (ver `tests/fixtures/logs/quiet_then_host_task2.py`):
     - tentar 921600 (HELLO 1,5 s); se não responder, 115200 (HELLO até 60 s);
     - em ambos, mandar antes `CMD_CHANNEL 13` sem esperar resposta;
     - depois do HELLO, `CMD_CHANNEL 13` com RESULT, e `CMD_BAUD 115200` se estava em 921600;
     - sempre `Radio.close()` num `finally` (o `open_serial` vaza a porta quando falha).
   - Integração: o `runner.child` (ou um wrapper `--module distrib.runners.session`) roda o quiet antes do `runpy` do host; o `frlg_session` também.
   - O `distrib.runners.hello` deve usar o mesmo quiet e terminar em 115200 (hoje usa `open_serial` com `fast_baud` padrão e deixa a placa em 921600).
4. **Log:** o `Tee-Object` do PowerShell grava UTF-16; o `swsh_v050.txt` já foi convertido para UTF-8. O Ctrl+C derruba o Tee antes de `stopping/served`, então a parada limpa fica para o aceite (no app, pelo fechamento do stdin).
