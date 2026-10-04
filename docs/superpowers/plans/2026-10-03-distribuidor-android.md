# Distribuidor no Android (APK): plano de execução

> **Spec:** `docs/superpowers/specs/2026-10-03-distribuidor-android-design.md` (aprovada em 2026-10-03).
> **Branch:** `android-spike` (já tem o spike Termux em `android_spike/` e o catálogo pré-validado). Ao fim, o merge vai para a `master` com o Release **v2.1.0**.
> **Fluxo:** Opus planeja e revisa pelo diff e pelos testes; Sonnet executa os lotes. As tarefas marcadas **[manual]** precisam do dono com o celular, a placa e o Switch.
> **Regra de ouro:** o `.exe` do Windows não pode mudar de comportamento. A suíte (`.venv/Scripts/python -m pytest -q`, hoje com 114 passando e 1 pulado) fica verde em todo commit.

## Contexto fixo (não reexplorar)

- Python do repo: `.venv/Scripts/python` (3.14.3), Flet **1.0.2**. pokeldn v0.5.0 em `vendor/pokeldn` (submódulo, `37410c1`). **Não editar `vendor/`.**
- **Processos-filhos hoje:**
  - `distrib/runner.py`: `command(*argv)` → `[sys.executable, ("-u", main.py)?, *argv]`; `child(argv, pokeldn_dir)` aquieta a placa e roda `--run bin/x.py ...` (via `runpy.run_path`) ou `--module m ...` (via `runpy.run_module`). Ela reconfigura o stdout e, com `DISTRIB_MANAGED_RUN`, cria uma thread que lê o stdin e, no EOF, faz `signal.raise_signal(SIGINT)`.
  - `distrib/distributor.py:125-132` (`_spawn`): `subprocess.Popen(job.argv, cwd=job.cwd, env=runner.child_env(job.env), **runner.popen_kwargs())`. Usa do Popen: `.stdout` (iteração por linha), `.poll()`, `.wait(timeout)`, `.returncode`, `.stdin.close()` (= parar com elegância), `.terminate()` e `.kill()`.
  - `distrib/radio.py:48` (`hello`): `subprocess.run(..., capture_output=True, timeout=75)` → `returncode`, `stdout`, `stderr`.
  - `distrib/board.py:43` (`flash`): `popen=subprocess.Popen` injetável; itera o `proc.stdout` e chama `proc.wait()`.
- **Serial:** o pokeldn abre a placa com `serial.Serial()` + `.port/.baudrate/.timeout/.dtr/.rts` + `.open()` (`vendor/pokeldn/pokeldn/ldn/esp32.py:274-310`), e o Radio usa `.read(4096)`, `.write(frame)`, `.flush()` e `.close()`. A placa liga a **115200**; o host sobe para **921600** com `CMD_BAUD`. O shim que já funciona está em `android_spike/android_env.py` (`FdSerial`) + `android_spike/hello_usb.py` (`UsbCdcSerial`, libusb via ctypes; **no APK não há libusb**).
- **Spike:** `android_spike/android_env.py` mostra as trocas que funcionaram: `POKELDN_RADIO=esp32:<qualquer>`, `POKELDN_L2=userspace` e `pokemon.SERVICE.validate_gift` pelo `android_spike/validated_index.lookup` com o `swsh_validated.json`. Também precisou do `python-netlink`, que vem com `pip install -e vendor/pokeldn/vendor/LDN`.
- O `distrib/runners/quiet.py` aquieta a placa (canal 13, HELLO e canal 13 de novo).
- O `distrib/runners/flash.py` faz `esptool.detect_chip(port)` e depois `esptool.main([... "--baud","460800","--after","hard-reset","write-flash","0x0",bin])`. Os firmwares ficam em `firmware/` (`pokeldn-radio.bin`, `-c3`, `-s3`, `-c6`).
- **App:** `main.py` (se `runner.is_child(argv)`, chama `runner.child`; senão abre a UI), `ui/app.py` (Flet: barra de título própria, barra lateral e views `ui/views/{inicio,distribuir,placa,ajustes}.py`), `distrib/service.py` (fachada; `Distributor(...)` na linha 170, `board.flash` na 266 e `update.*` nas 280-294), `distrib/update.py` (`ASSET="Distribuidor.exe"`, `REPO`, `latest/newer/download/apply`), `distrib/config.py` (`default_data_dir()`, `resource_root()`) e `distrib/download.py` (`GALLERY_URL`, `update_catalogs`).
- **Celular do dono:** Android 16 (SDK 36), arm64. Placa ESP32 clássica com CH9102 (VID `1a86`, CDC-ACM: `comm_if=0`, `data_if=1`, `ep_in=0x82`, `ep_out=0x02`). Para levar o APK ao celular: **SendUserFile** (o dono está remoto e instala direto do app do Claude).

---

## Fase 0: provas dos riscos dentro de um APK (`android/probe/`)

Um app Flet mínimo e separado (`android/probe/main.py` + `android/probe/pyproject.toml`), com um botão por risco e a saída na tela, em texto selecionável. O código que passar nas provas é o mesmo que a Fase 1 move para `distrib/platform/`.

### Task A1: toolchain do `flet build apk`
- Criar `android/probe/` com um app Flet de um botão ("ping") e um `pyproject.toml` com `[project] name="distrib-probe"`, `dependencies=["flet==1.0.2"]` e `[tool.flet] app.module="main"`, com `[tool.flet.android]` só para `arm64-v8a`.
- Rodar `flet build apk` (de dentro de `android/probe`, com o `flet` da `.venv`). Ele baixa Flutter, JDK e Android SDK na primeira vez: anotar o tempo e os caminhos. Se pedir aceite de licença do SDK, aceitar.
- **Aceite:** `android/probe/build/apk/*.apk` gerado. Registrar no fim do plano (seção *Notas de execução*) a versão do Python embutido no APK (`sys.version`, que o botão "ping" mostra) e o `sys.platform`.

### Task A2: USB pelo pyjnius (`android/probe/usb_android.py`)
- Dependência `pyjnius` (índice do Flet). Implementar `AndroidUsbSerial(device_name=None, baud=115200)`:
  - `UsbManager` via `autoclass('org.kivy.android.PythonActivity')` **ou** o equivalente do Flet. Descobrir qual classe de Activity o Flet expõe (procurar "pyjnius" nas docs do Flet 1.0: https://flet.dev/blog/tap-into-native-android-and-ios-apis-with-Pyjnius-and-pyobjus) e registrar nas *Notas*.
  - Escolher o dispositivo por VID em `{0x1a86, 0x10c4, 0x0403, 0x303a}`.
  - `requestPermission(device, PendingIntent.getBroadcast(ctx, 0, Intent("dev.distrib.USB_PERMISSION"), FLAG_IMMUTABLE))`, depois polling de `hasPermission` por até 30 s.
  - `openDevice` e `claimInterface` (comm e data). As interfaces e os endpoints saem da API Java (`getInterface(i).getInterfaceClass()` 0x02/0x0A e `getEndpoint(j)` com `getType()==USB_ENDPOINT_XFER_BULK` e a direção).
  - `controlTransfer(0x21, 0x20, 0, comm_if, line_coding, 7, 1000)` e `controlTransfer(0x21, 0x22, (dtr|rts<<1), comm_if, None, 0, 1000)`.
  - `read(size, timeout_ms)` / `write(data)` por `bulkTransfer`.
  - Interface Python idêntica à `UsbCdcSerial` do spike, mais `set_baud`, `set_lines(dtr, rts)` e `close`.
- Botão **HELLO**: o mesmo protocolo do `android_spike/hello_usb.py` (frame `06 01 1B DF 05 A5 00`, ler até achar `MSG_INFO` 0x81). Mostra o texto do firmware.
- Botão **BENCH**: instalar o shim (como em `android_env.FdSerial`, agora sobre `AndroidUsbSerial`) em `serial.Serial`, abrir `esp32.Radio.open_serial("usb")` (sobe para 921600) e rodar `radio.bench(400_000)`. Mostra `rate`, `missing` e `rejected`.
- **[manual] Aceite:** HELLO ok, e BENCH com `missing == 0` e taxa ≥ 60 KB/s. **Plano B,** se a taxa ficar baixa por causa do JNI: `connection.getFileDescriptor()` + ioctls do usbfs (`USBDEVFS_BULK = _IOWR('U', 2, struct usbdevfs_bulktransfer)`) em Python puro via `fcntl.ioctl`, só para os bulk. Registrar a taxa nas *Notas*.

### Task A3: `unicorn` no APK
- Compilar o `libunicorn.so` do unicorn **2.1.4** com o NDK que o `flet build` instalou (ou instalar via `sdkmanager "ndk;<versão>"`): `cmake -DCMAKE_TOOLCHAIN_FILE=$NDK/build/cmake/android.toolchain.cmake -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-24 -DUNICORN_ARCH="arm;aarch64" -DCMAKE_BUILD_TYPE=Release`.
- Montar `android/wheels/unicorn-2.1.4-py3-none-android_24_arm64_v8a.whl` com o binding Python puro do sdist 2.1.4 (`bindings/python/unicorn/`) e a `.so` onde o binding procura (`unicorn/lib/libunicorn.so`). Conferir no `unicorn/unicorn.py` do sdist os caminhos de busca.
- Fazer o `flet build` usar o wheel local. Testar nesta ordem e registrar o que funcionou:
  1. `dependencies` com caminho de arquivo;
  2. `--source-packages` ou a opção equivalente do Flet 1.0;
  3. índice local com `pip --find-links`.
- Botão **unicorn**: emular `mov r0, #42` (ARM) e mostrar `r0`.
- **[manual] Aceite:** a tela mostra `r0=42`.

### Task A4: esptool pelo USB do Android
- O shim de A2 com `dtr`/`rts` funcionando (`set_lines`). Antes do esptool, trocar `serial.Serial` e `serial.serial_for_url` pelo shim.
- Forçar o reset clássico: conferir no esptool 5.x instalado (`.venv/Lib/site-packages/esptool/reset.py` e `loader.py`) como ele escolhe entre `UnixTightReset` e `ClassicReset`. A forma preferida é a opção/configuração oficial (`--before`, arquivo de config `esptool.cfg` com `custom_reset_sequence`). Monkeypatch só como último recurso. Registrar nas *Notas*.
- Botão **chip**: `esptool.detect_chip("usb")` mostra o chip. Botão **gravar**: `distrib.runners.flash.main(["usb", <pasta firmware embutida>])`.
- **[manual] Aceite:** detecta "ESP32", grava a 460800 e, depois do hard-reset, o HELLO volta a responder. Se a gravação falhar no meio, a placa **não estraga** (o bootloader fica na ROM): gravar de novo pelo celular ou pelo `.exe`.

**Ponto de decisão (Opus + dono):** se A2 ou A3 falharem sem plano B viável, parar e reavaliar a spec antes da Fase 1.

---

## Fase 1: camada de plataforma no `distrib/` (testável no PC)

### Task B1: detectar Android + rodar filhos em thread
- `distrib/platform/__init__.py`: `IS_ANDROID = sys.platform == "android" or "ANDROID_DATA" in os.environ` (usar o `sys.platform` anotado em A1).
- `distrib/platform/inproc.py`:
  - `InProcPopen(argv, cwd=None, env=None, **_)`, que imita o subconjunto do Popen listado no *Contexto*. Recorta `argv` a partir do primeiro token em `runner.MODES`. Aplica `env` (só as chaves que diferem de `os.environ`, restaurando no fim; um job por vez). Roda `runner.child(argv, pokeldn_dir, inproc=True)` numa thread `daemon`.
  - O stdout/stderr daquela thread vai para uma fila. Isso vem de um proxy instalado **uma vez** em `sys.stdout`/`sys.stderr`, que encaminha por `threading.get_ident()` e manda o resto ao stream original. `.stdout` é um iterável de linhas (com `\n`) que termina quando a thread acaba.
  - `.stdin.close()` → `ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(tid), ctypes.py_object(KeyboardInterrupt))`. `.terminate()` faz o mesmo; `.kill()` faz o mesmo e marca `returncode=-9` se a thread não sair em 5 s.
  - `returncode` vem do `SystemExit.code` (int; `None` vira 0, str vira 1), de uma exceção (vira 1) ou é 0.
  - `inproc.run(argv, cwd=None, env=None, timeout=None, **_)` devolve um objeto com `returncode`, `stdout` e `stderr` (str), com `subprocess.TimeoutExpired` em caso de timeout.
- `runner.child(argv, pokeldn_dir, inproc=False)`: com `inproc=True`, pula o `reconfigure` e a thread do stdin. O resto fica igual.
- `runner.popen` e `runner.run`: são `inproc.InProcPopen` / `inproc.run` quando `IS_ANDROID`, e `subprocess.Popen` / `subprocess.run` caso contrário.
- **Testes** (`tests/test_inproc.py`): criar `tests/fixtures/inproc_child.py`, um módulo que imprime 3 linhas, depois fica em `while True: time.sleep(0.01)` e, ao receber `KeyboardInterrupt`, imprime "parado" e sai com `sys.exit(0)`. Testar:
  - leitura das linhas;
  - parada por `stdin.close()` com o `returncode` 0 e a linha "parado";
  - `SystemExit(3)` → `returncode` 3;
  - exceção → 1;
  - `run()` com captura e com timeout.
- **Aceite:** testes novos verdes e suíte verde.

### Task B2: usar `runner.popen`/`runner.run` nos três pontos
- `distributor.py:131`: `subprocess.Popen(` → `runner.popen(`. `radio.hello`: o default `run=subprocess.run` vira `run=None`, resolvido para `runner.run` no corpo. `board.flash`: idem com `popen=None` → `runner.popen`.
- No desktop, `runner.popen is subprocess.Popen`. Garantir isso com um teste (`IS_ANDROID` falso no PC).
- **Aceite:** suíte verde, sem mudar testes existentes (os que injetam fakes continuam injetando).

### Task B3: serial Android dentro do `distrib/`
- Mover o `AndroidUsbSerial` aprovado em A2 (e o plano B, se usado) para `distrib/platform/android_usb.py`. Criar ali também:
  - `install_serial_shim()`: troca `serial.Serial` e `serial.serial_for_url` por uma classe pyserial-like sobre um único `AndroidUsbSerial` por processo, como o `FdSerial` do spike, mais `dtr`/`rts` via `set_lines`;
  - `list_ports()`: devolve objetos com `.device="usb:<deviceName>"`, `.vid`, `.pid` e `.description`, no formato que o `radio.list_boards` espera (conferir os atributos que ele lê).
- O acesso ao pyjnius fica atrás de uma fachada `_Java` injetável. Os testes no PC usam um fake que simula a placa: responde ao HELLO e conta bytes.
- `radio.list_boards`/`find_port` e `Service(comports=...)` usam `android_usb.list_ports` quando `IS_ANDROID`.
- **Testes:** `tests/test_android_usb.py`, com o fake `_Java`: abrir, `set_baud`, `set_lines`, ler/escrever e `list_ports`.

### Task B4: caminhos, PKHeX offline, tela ligada
- `config.default_data_dir()`: no Android, `Path(os.environ["FLET_APP_STORAGE_DATA"])` (confirmar o nome da variável em A1; registrar nas *Notas*). `resource_root()`: conferir se os assets/firmware embutidos ficam acessíveis no APK (A4 já usa a pasta de firmware embutida).
- Mover `android_spike/validated_index.py` para `distrib/validated_index.py`. Criar `distrib/platform/android_env.py` com `apply(cfg)`, que no Android:
  - define `POKELDN_L2=userspace`;
  - troca `pokemon.SERVICE.validate_gift` pelo lookup no `swsh_validated.json`, que fica em `cfg.data_dir` (baixado) com fallback para o embutido;
  - chama `install_serial_shim()`.
- **Revisão do B1 (Opus):** o `InProcPopen` passa o `cwd` do job como `pokeldn_dir` do `runner.child` e não faz `chdir`; hoje todo job tem `cwd=cfg.pokeldn_dir`, então funciona. No Android, o `apply` precisa fazer `os.chdir(cfg.pokeldn_dir)` uma vez, como o spike fazia, porque os hosts usam caminhos relativos ao pokeldn.
- Chamar `apply` no início do app quando `IS_ANDROID` (`ui/app.py`, antes de criar o `Service`) e também no `runner.child(inproc=True)`, por idempotência.
- `keep_screen_on(on: bool)` via pyjnius (`FLAG_KEEP_SCREEN_ON` na janela da Activity, na thread de UI do Android: `runOnUiThread` via `PythonJavaClass` Runnable). O `Service` liga ao começar a distribuir e desliga ao parar. No desktop não faz nada.
- **Testes:** o lookup (mover os testes de `tests/test_prevalidate.py`) e `apply` com `IS_ANDROID` simulado e o `pokemon` falso.

### Task B5: atualização e catálogo no Android
- `update.py`: `ASSET` vira `asset_name()` → `"Distribuidor.apk"` no Android e `"Distribuidor.exe"` fora dele. No Android, `Service` não baixa nem aplica: o aviso da UI abre `release.url_html` (acrescentar `html_url` ao `Release`) com `page.launch_url`.
- `download.update_catalogs`: no Android, depois de extrair, baixa `swsh_validated.json` do Release mais recente (asset com esse nome) para `cfg.data_dir`. Se falhar, mantém o embutido. A grade do SwSh mostra **só** os aprovados. Os recusados não aparecem, e uma linha discreta diz "N eventos ocultos (recusados pelo PKHeX)".
- **Testes:** `asset_name`, o download do JSON com o opener falso e o filtro da grade (no adapter `distrib/games/swsh.py`, onde os eventos são listados).

---

## Fase 2: interface móvel

### Task C1: layout responsivo
- Em `ui/app.py`, quando `IS_ANDROID` (ou largura < 700):
  - sem a barra de título própria;
  - `ft.NavigationBar` embaixo com os mesmos 4 destinos;
  - o cartão da placa vira uma faixa compacta no topo;
  - a grade de Pokémon em `distribuir.py` com `runs_count`/`max_extent` adaptados.
- O desktop fica idêntico: conferir pelo diff que os ramos desktop não mudaram.
- O seletor de `prod.keys` (`ft.FilePicker`) funciona no Android: o arquivo vem como bytes ou caminho temporário e é copiado pelo `Service.set_keys`.
- **[manual] Aceite:** as 4 telas no celular, sem nada cortado, em retrato.

---

## Fase 3: empacotamento, aceite e release

### Task D1: build do APK do app real
- `pyproject.toml` na raiz para o `flet build`. Ele não pode afetar o `build/pack.py` do `.exe`; se conflitar, usar um diretório de staging como o `.pack/` do `.exe`. Conteúdo:
  - `app.module="main"`;
  - dependências: `flet`, `pyserial`, `esptool`, `pycryptodome`, `zstandard`, `trio`, `pyjnius`, `python-netlink` e o wheel do `unicorn` de A3;
  - `[tool.flet.android.feature] "android.hardware.usb.host" = true`;
  - intent-filter `USB_DEVICE_ATTACHED` + `device_filter.xml` com os VIDs (pelo template do build, como achado em A1/A2);
  - ícone da Poké Ball (`ui/assets/pokeball.svg`, convertido para PNG se o Flet exigir).
- `build/pack_android.py`:
  1. regenera `android_spike/swsh_validated.json` → `distrib/data/swsh_validated.json` (`build/prevalidate_swsh.py` com a saída nova);
  2. monta o staging com `distrib/`, `ui/`, `main.py`, `firmware/` e o pokeldn v0.5.0 **sem** `services/pkhex`;
  3. roda `flet build apk --arch arm64-v8a`;
  4. copia para `dist/Distribuidor.apk`.
- README: seção "Android", com OTG, instalação do APK (permitir fontes desconhecidas) e o hub com energia se o celular não alimentar a placa.
- **Aceite:** `dist/Distribuidor.apk` gerado e a suíte verde.

### Task D2 [manual]: aceite no celular
Pelo APK, enviado com SendUserFile:
1. instalar;
2. escolher o `prod.keys`;
3. "Preparar placa";
4. "Baixar eventos";
5. distribuir um evento SwSh ainda não recebido e conferir no Sword;
6. Parar;
7. distribuir um `.pk3` ao FireRed (com Pausar/Retomar);
8. plugar a placa com o app fechado e ver o Android oferecer abrir o app.

Gravar os logs do app em `tests/fixtures/logs/android_v210_*.txt`.

### Task D3: Release v2.1.0 e merge
- `distrib/__init__.py` → `2.1.0`.
- Regerar o `.exe` (`build/pack.py`) e o `.apk`, e confirmar que o `.exe` ainda abre e conecta. **[manual]** Esse teste exige o PC; se o dono estiver remoto, publicar só depois.
- Merge de `android-spike` na `master`. A pasta `android_spike/` fica como histórico ou é removida; o que sobrou de útil já está em `distrib/`.
- Release `v2.1.0` com os assets `Distribuidor.exe`, `Distribuidor.apk` e `swsh_validated.json`, e notas em pt-BR.
- Atualizar o vault (`Tasks/pokeldn.md` e o log da sessão).

---

## Lotes sugeridos para o Sonnet

| Lote | Tasks | Depende de |
|---|---|---|
| 0a | A1 | — |
| 0b | A2, A3, A4 (código das provas + APK) | A1; aceite **[manual]** |
| 1 | B1, B2 | — (pode correr junto do 0b) |
| 2 | B3, B4, B5 | 0b aprovado |
| 3 | C1, D1 | 2 |
| — | D2 **[manual]**, D3 | 3 |

## Notas de execução
- **A1 (parcial, BLOQUEADA)**: `android/probe/` criado (main.py + pyproject.toml; arch via `[tool.flet.android] target_arch=["arm64-v8a"]`). `flet build apk --yes` no PC (~5 min até a falha) instalou Flutter 3.44.8 em `C:\Users\gabry\flutter\3.44.8`, JDK Temurin 17.0.13+11 em `C:\Users\gabry\java\17.0.13+11` e Android SDK em `C:\Users\gabry\Android\sdk` (licenças aceitas via `--yes`). O Flet embute Python 3.14 (CPython 3.14.7) no Android (`--python-version 3.14` no log). Exige `PYTHONUTF8=1` no Windows (senão UnicodeEncodeError cp1252 no log). **Falha**: "Building with plugins requires symlink support. Please enable Developer Mode": o usuário do Windows não é admin e não tem privilégio de symlink; é preciso ligar o Modo Desenvolvedor (Configurações > Para desenvolvedores) ou rodar como admin. APK ainda não gerado; NDK e `sys.platform` pendentes.
(preencher durante a execução: Python e `sys.platform` do APK, classe da Activity no pyjnius, variável do diretório de dados, taxa do BENCH, como o wheel local entrou no build, como o reset clássico foi forçado)
- A1 (2026-10-03): o build no Windows exige symlinks (Modo Desenvolvedor), então foi para o **GitHub Actions** (`.github/workflows/android-probe.yml`, ubuntu-latest, Python 3.14 + Temurin 17). Run `37151520235` ok: `distrib-probe.apk` com 54,8 MB, CPython 3.14.7 embutido. O dono baixa o artifact (zip) pelo GitHub logado no celular. Falta a saída do botão ping (`sys.platform`, variáveis do diretório de dados).
