# Plano — Distribuidor no macOS (Apple Silicon)

Spec: `docs/superpowers/specs/2026-11-16-distribuidor-macos-design.md` (aprovada em 2026-11-16).
Branch: `macos` (a partir da `master`). Python 3.14; testes: `python -m pytest -q -p no:cacheprovider` (hoje 162 passam e 1 é pulado no Linux; no Windows, rode e anote a linha de base antes de mudar).
Regra: o distrib (MIT) **importa ou executa** o pokeldn (AGPL) em `vendor/pokeldn`, **sem copiar código dele**. Nunca editar `vendor/pokeldn`.

Fatos já verificados:
- No macOS o pokeldn usa `userspace` por padrão (`esp32_wlan.py:455`), então o `child_env` do `distrib/runner.py` **não muda**.
- O `serial.tools.list_ports` do macOS só lista `/dev/cu.*`. As portas Bluetooth vêm com `vid=None` e o `list_boards` já as descarta. O `radio.list_boards` **não muda**.
- O upstream empacota o Mac com `vendor/pokeldn/scripts/pack_flet.py` (troca o `assemble_app_bundle` do Flet para manter o entitlement do seletor de arquivos) e `vendor/pokeldn/scripts/pack_app.py` (linhas 60–115: patch do `list_ports_osx`, `--bundle-id`, Info.plist, `codesign --deep --sign -`). O `scripts/check_app.py` (linhas 9–45) confere o entitlement.

---

## Lote 1 — código e testes (Sonnet; roda no Windows, sem Mac)

### T1. Flags e caminhos do macOS
1. `distrib/platform/__init__.py`: `IS_MACOS = sys.platform == "darwin"`.
2. `distrib/config.py::default_data_dir`: antes do `return legacy`, se `sys.platform == "darwin"` e o `legacy` não existir, devolver `Path.home() / "Library" / "Application Support" / APP_NAME`. Os ramos de Android, `LOCALAPPDATA` e Linux não mudam.
3. `distrib/pokeldn_path.py`: a condição vira `sys.platform in ("win32", "linux", "darwin")`.
4. `ui/views/ajustes.py::_logs`: no `darwin`, o mesmo `Popen` com `["open", caminho]` em vez de `xdg-open`.
5. `distrib/radio.py`: criar `MACOS_HINT = ("No macOS os drivers de CP210x, CH340 e CH9102 já vêm no sistema (macOS 11 ou mais novo); a porta aparece como /dev/cu.usbserial-* ou /dev/cu.wchusbserial*. Se não aparecer, troque o cabo (tem que ser de dados) e replugue a placa.")`. Em `ui/views/placa.py::_drivers`, no `darwin`, mostrar um card igual ao do Linux, com o `MACOS_HINT`.
6. Testes em `tests/test_config.py` (data dir no darwin, com `monkeypatch` de `sys.platform`, `LOCALAPPDATA` removido e `HOME`/`Path.home` em `tmp_path`; e o legacy preservado quando existe) e em `tests/test_main.py` ou num arquivo novo (o `ensure_importable` define `POKELDN_PKHEX` no darwin quando o binário existe).

**Aceite:** os testes novos passam e a linha de base não piora.

### T2. Atualização no macOS: baixa, confere e mostra no Finder
1. `distrib/update.py`:
   - `IS_MACOS = sys.platform == "darwin" and not IS_ANDROID`.
   - `asset_name()`: no macOS, `"Distribuidor-macos-arm64.zip"`.
   - `download()`: o nome final vira `Distribuidor-{tag}.zip` no macOS. Hoje ele usa `.AppImage` ou `.exe`: extrair um helper `_suffix()`.
   - nova `reveal(path, launch=subprocess.Popen)`: `launch(["open", "-R", str(path)], close_fds=True)`.
   - `apply()` **não** é chamado no macOS.
2. `distrib/service.py::apply_update`: no macOS (`update.IS_MACOS`), se `_ready_update` existir, chamar `update.reveal(self._ready_update)` e devolver **False** (o app não fecha). Em `OSError`, `update_state="error"`.
3. `ui/app.py`:
   - em `run()`, o `exe` congelado no macOS é `Path(sys.executable)` (o padrão atual já serve, porque `update.cleanup` é inofensivo);
   - `_update_row`: no estado pronto, no macOS, o texto é `"Atualização {v} baixada."` mais `t.muted("Extraia o .zip e troque o app na pasta Aplicativos.")`, e o botão `"Mostrar no Finder"` chama `self.service.apply_update()` (sem fechar a janela);
   - texto de erro sem `.exe`: `"A atualização falhou. Baixe a versão nova no GitHub e substitua o app."`.
4. Testes em `tests/test_update.py`, seguindo o padrão do `test_linux_*` (monkeypatch de `IS_MACOS`/`IS_LINUX`): asset do Mac, sufixo `.zip`, `reveal` chama `open -R`. Em `tests/test_service.py`: no macOS, o `apply_update` revela e devolve False.

**Aceite:** os testes passam; no Windows e no Linux o comportamento fica idêntico (os testes existentes não mudam).

### T3. Runner `selfcheck` (smoke test do app congelado, sem placa)
`distrib/runners/selfcheck.py`, rodado como `Distribuidor --module distrib.runners.selfcheck`. Ele:
- importa `serial.tools.list_ports` e chama `comports()`;
- importa `swsh_gift_host` e `frlg_mg_host`;
- confere que `os.environ["POKELDN_PKHEX"]` existe e é executável (`os.access(..., os.X_OK)`), exceto no Android;
- confere que os firmwares de `distrib.board.FIRMWARE` existem em `load().firmware_dir`;
- imprime `selfcheck ok` e sai com 0; em caso de falha, imprime o motivo e sai com 1.

Siga a forma do `distrib/runners/hello.py`. Inclua um teste que roda o `main` dele pelo código-fonte, aceitando o PKHeX ausente via monkeypatch, se precisar.

**Aceite:** `python main.py --module distrib.runners.selfcheck` no Windows imprime `selfcheck ok` ou uma falha explicada (sem PKHeX compilado localmente, aceita-se a falha do PKHeX).

Commits: um por task, na branch `macos`.

---

## Lote 2 — build e CI (Sonnet; validado no CI do GitHub, `macos-14`)

### T4. Ícone `.icns`
`build/make_icon.py` também salva `ui/assets/icon.icns` (`img.save(OUT.with_suffix(".icns"))`; o Pillow gera ICNS em qualquer sistema). Rodar o script e commitar o `.icns`.

### T5. `build/pack.py` no darwin
- `MAC = sys.platform == "darwin"`. RID do PKHeX: `osx-arm64` no Mac, binário `pokeldn-pkhex`.
- No Mac, o comando do packer é `[sys.executable, str(POKELDN / "scripts" / "pack_flet.py"), "pack", ...]` (o script do upstream é **executado**, não copiado). Nos outros sistemas continua o `-c FLET`.
- Argumentos no Mac: `--icon ui/assets/icon.icns`, `--product-name "Distribuidor de Eventos"`, `--product-version`, `--file-version`, `--bundle-id com.carlosgabryel.distribuidor`. Sem `--console`.
- Patch do `list_ports_osx`, como no `pack_app.py` do upstream (linhas 69–78): copiar o pacote `serial` para `WORK / "deps"` com o `list_ports_osx.py` alterado, e pôr `--paths={WORK/'deps'}` **antes** dos outros `--paths` (as linhas são do upstream; o distrib reimplementa com o próprio código, a mesma ideia de 6 linhas).
- Depois do pack: `dist/Distribuidor.app` precisa existir. Atualizar o `Info.plist` (`CFBundleShortVersionString`/`CFBundleVersion` = `__version__`), rodar `codesign --force --deep --sign - dist/Distribuidor.app` e `ditto -c -k --keepParent dist/Distribuidor.app dist/Distribuidor-macos-arm64.zip`.
- Docstring e mensagens de erro passam a citar o Mac.

### T6. `build/check_macos.py`
Confere no `dist/Distribuidor.app`: (a) o entitlement `com.apple.security.files.user-selected.read-write` no viewer do Flet, extraído do `flet-macos.tar.gz` de dentro do bundle (como no `vendor/pokeldn/scripts/check_app.py` linhas 28–42, com o caminho achado por `rglob("flet-macos.tar.gz")`); (b) `codesign --verify --deep --strict`; (c) roda `Contents/MacOS/Distribuidor --module distrib.runners.selfcheck` e exige `selfcheck ok`.

### T7. CI
`.github/workflows/release.yml`:
- novo job `build-macos` (`runs-on: macos-14`, **`continue-on-error: true`**), com os passos do `build` mais os `Testes` (pytest), `python build/pack.py`, `python build/check_macos.py` e o upload do artifact `Distribuidor-macos-arm64.zip`;
- o job `release` passa a ter `needs: [build, android, build-macos]` e `if: always() && startsWith(github.ref, 'refs/tags/v') && needs.build.result == 'success' && needs.android.result == 'success'`. Assim, **um Mac quebrado não trava a release** das outras plataformas;
- no `gh release create`, anexar `assets/Distribuidor-macos-arm64.zip` só se o arquivo existir (montar a lista num array do bash);
- no job `build` (Linux), depois do pack, rodar o selfcheck no binário `dist/Distribuidor` antes do AppImage (opcional; se complicar, pular e anotar).

### T8. README
Seção "macOS (Apple Silicon)": baixar o `Distribuidor-macos-arm64.zip`, extrair e mover para Aplicativos; na 1ª abertura, ir em Ajustes > Privacidade e Segurança > "Abrir mesmo assim", ou rodar `xattr -dr com.apple.quarantine /Applications/Distribuidor.app`; os drivers já vêm no sistema; Intel não é suportado; as atualizações baixam o `.zip` e o mostram no Finder.

**Aceite do lote 2:** `gh workflow run release.yml --ref macos` → o job `build-macos` fica verde e gera o artifact `.zip`; os jobs `build` e `android` continuam verdes. Iterar pelos logs do CI (`gh run view --log-failed | tail -80`).

---

## Lote 3 — aceite real (testador com Mac; Opus coordena)
Mandar ao dono o `.zip` do artifact e o roteiro de 7 passos da spec. Correções viram tasks pequenas. Depois do aceite: subir a versão (`distrib/__init__.py` e `android/app/pyproject.toml`), criar a tag e publicar a release com notas (Mac "experimental" até o primeiro aceite completo).
