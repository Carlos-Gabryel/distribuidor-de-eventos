# Distribuidor no Android (APK) — design

**Data:** 2026-10-03 · **Estado:** rascunho para aprovação do dono · **Base:** prova de viabilidade em `docs/superpowers/plans/2026-10-03-android-viabilidade.md` (SwSh e FRLG entregues pelo celular via Termux; branch `android-spike`).

## Objetivo

Um **APK** do Distribuidor de Eventos que faz no celular Android o mesmo que o `.exe` v2.0.0 faz no Windows. A ESP32 vai no USB-C por OTG, sem root, sem Termux e sem PC.

## Decisões (tomadas com o dono em 2026-10-03)

| Tema | Decisão |
|---|---|
| Distribuição | APK no **GitHub Releases** do mesmo repo, ao lado do `.exe`. Fora da Play Store, que tende a recusar apps que usam chaves do Switch. |
| Escopo v1 | Paridade com o `.exe`: Mystery Gift de **SwSh** e **FRLG**, "Baixar eventos", seletor de `prod.keys` e **"Preparar placa" (gravar firmware) já na v1**. |
| Código | **Mesmo repositório.** `distrib/` e `ui/` são compartilhados; só entram uma camada de plataforma (USB, execução, caminhos) e o layout móvel. |
| Interface | Flet (o mesmo do `.exe`), empacotado com `flet build apk`. |
| ABI | Só **arm64-v8a** (todo Android atual; simplifica o `unicorn`). |
| PKHeX | Não roda no celular. O SwSh usa o **catálogo pré-validado no PC** (`swsh_validated.json`, passo 3 do spike). |

## O que a prova já garantiu

- O celular alimenta a placa pelo OTG, e a serial CDC-ACM (CH9102, `comm_if=0 data_if=1 ep_in=0x82 ep_out=0x02`) funciona sem root, a partir de um fd do Android.
- O host do pokeldn v0.5.0 roda no Android com L2 `userspace`, com `python-netlink` só importado.
- `pycryptodome`, `zstandard`, `trio` e `unicorn` funcionam em arm64 (no Termux).
- SwSh: 100 Poké Balls. FRLG: WISHMKR Jirachi (`status 2 (success)`).

## O que muda em relação ao `.exe`

### 1. USB: `distrib/platform/android_usb.py`

- **Permissão e abertura:** via **pyjnius** (há wheel pronto no índice do Flet): `UsbManager.getDeviceList()` → filtro por VID/PID de pontes conhecidas (CH9102/CH340 `1a86`, CP210x `10c4`, FTDI `0403`, ESP32-S3 nativo `303a`) → `requestPermission(device, PendingIntent)` → polling de `hasPermission`, com timeout. Sem BroadcastReceiver, que no pyjnius exigiria uma classe Java. Também um *intent-filter* `USB_DEVICE_ATTACHED` com `device_filter.xml`: assim o Android oferece abrir o app ao plugar a placa, e a permissão já vem concedida.
- **Transferências:** `UsbDeviceConnection.openDevice` → `claimInterface` → `controlTransfer` (SET_LINE_CODING / SET_CONTROL_LINE_STATE) e `bulkTransfer`, todos pelo pyjnius. **Se** o custo do JNI por chamada não sustentar 921600 baud, o plano B é usar `getFileDescriptor()` com ioctls do usbfs (`USBDEVFS_BULK`, `USBDEVFS_CONTROL`) em Python puro, sem libusb (o Flet não tem libusb pronto).
- **Shim pyserial:** a classe `FdSerial` do spike (`android_spike/android_env.py`) vira `AndroidSerial`, com `dtr`/`rts` de verdade, que o esptool usa. É instalada em `serial.Serial` e `serial.serial_for_url` no início do app no Android.
- `radio.list_boards()` ganha uma implementação Android que devolve `Port(device="usb:<deviceName>", description="ESP32 (CH9102)")`.

### 2. Execução: do processo-filho para a thread (`distrib/platform/inproc.py`)

No APK não existe executável `python` para criar processos-filhos, e o `.exe` roda tudo como filho (`runner.command` + `subprocess.Popen`). No Android:
- `runner.child(argv)` (já é o ponto de entrada dos filhos) roda numa **thread**. O stdout dela vai para um *writer* por thread (um proxy de `sys.stdout` que encaminha pela thread de origem) e alimenta o mesmo `parse_line` de hoje.
- **Parar:** hoje é SIGINT. Na thread, a primeira opção é `PyThreadState_SetAsyncExc(KeyboardInterrupt)`, que o host já trata como "parar". Os hosts estão em laço Python (trio), então a exceção chega. Se uma chamada bloqueante segurar por muito tempo, o shim USB usa timeouts curtos (já é o caso: 20 ms).
- `Distributor`, `radio.hello` e `board.flash` recebem um **launcher** injetável: `SubprocessLauncher` no desktop (o comportamento de hoje, intacto) e `ThreadLauncher` no Android. Só um job por vez, como hoje.
- O "aquietar a placa" (`runners/quiet.py`) continua igual, agora pela serial do Android.

### 3. Firmware ("Preparar placa")

- `runners/flash.py` (esptool) roda na thread, sobre o `AndroidSerial`. A entrada no bootloader é a sequência clássica DTR/RTS via `SET_CONTROL_LINE_STATE`.
- **Risco:** fora do Windows, o esptool tenta o `UnixTightReset`, que usa `fcntl.ioctl` no `fileno()` e não existe no nosso shim. É preciso forçar o reset clássico (`--before` / estratégia de reset por config) e confirmar que a troca para 460800 baud funciona no CH9102.
- Os firmwares (`ui/assets/firmware/*`) vão dentro do APK, como no `.exe`.

### 4. `unicorn` (FRLG)

Não há wheel do `unicorn` no índice do Flet. O binding Python do unicorn usa **ctypes sobre `libunicorn.so`**. Por isso:
- compilar `libunicorn.so` 2.1.4 com o **Android NDK** (CMake, arm64-v8a, só o backend ARM, que é o que o FRLG usa);
- montar um wheel local `unicorn-2.1.4-py3-none-android_24_arm64_v8a.whl` com o binding e a `.so`;
- informar ao `flet build` (receita do mobile-forge ou índice local). Se o Flet não aceitar wheel local, a alternativa é publicar a receita no mobile-forge.

### 5. PKHeX → catálogo pré-validado

- No Android, `pokemon.SERVICE.validate_gift` vem do `validated_index.lookup` (spike, `c4342ab`).
- O `swsh_validated.json` vai **dentro do APK** e também como **asset do Release**. O "Baixar eventos" no celular baixa o Events Gallery e o JSON do Release mais recente. Cartões fora da lista não aparecem na grade, ou aparecem com o motivo.
- `build/pack_android.py` regenera o JSON (PKHeX no PC) a cada build.

### 6. Caminhos, chaves e atualização

- `config.default_data_dir()` no Android: o armazenamento do app (`FLET_APP_STORAGE_DATA`).
- `prod.keys`: o seletor de arquivos do Flet copia o arquivo para o armazenamento do app (o mesmo `Service.set_keys`).
- **Atualização:** `update.py` passa a ter um asset por plataforma (`Distribuidor.exe` / `Distribuidor.apk`). No Android, v1 só **avisa** e abre o link do APK no navegador; o Android cuida da instalação. Instalação dentro do app fica para depois (exige `REQUEST_INSTALL_PACKAGES`).
- Durante a distribuição a tela fica ligada (`FLAG_KEEP_SCREEN_ON` via pyjnius), para o Android não suspender o app.

### 7. Interface móvel

- Mesmas telas (Início, Distribuir, Placa, Ajustes) e mesmo fluxo de Distribuir (Jogo → grade por Pokémon → eventos → distribuindo).
- Em largura de celular, a **barra lateral vira barra de navegação inferior** e o cartão da placa vira uma faixa compacta no topo. A grade de Pokémon se ajusta ao número de colunas.
- A barra de título própria do `.exe` não existe no Android (é desktop).

### 8. Empacotamento e licença

- `pyproject.toml` com `[tool.flet]`: `android.hardware.usb.host = true`, intent-filter e `device_filter.xml`, `--arch arm64-v8a`. Dependências: `pycryptodome`, `zstandard`, `trio`, `pyserial`, `esptool`, `pyjnius` e `python-netlink` (puros ou do índice do Flet), mais o wheel local do `unicorn`. O pokeldn v0.5.0 vai sem `services/pkhex`.
- Python embutido: a mesma linha do `.exe` (3.14) se o Flet a oferecer para Android; senão, a mais nova que oferecer, e roda-se a suíte de testes nessa versão.
- O pokeldn é AGPL-3.0. O APK embute o pokeldn, então o repositório (público) precisa trazer o código correspondente a cada release, como já acontece com o `.exe`.

## Riscos, em ordem (cada um vira um spike curto no início do plano)

1. **USB pelo pyjnius dentro do APK** (permissão + bulk a 921600). Plano B: usbfs por ioctl.
2. **`unicorn` no `flet build`** (wheel local / receita).
3. **esptool pelo USB do Android** (reset clássico, troca de baud).
4. **Host em thread** (parar por exceção assíncrona; o proxy de stdout por thread).
5. Energia do OTG em celulares fracos: documentar o hub OTG com energia externa.

## Fora do escopo da v1

Play Store; iPhone; atualização instalada pelo próprio app; outros jogos além de SwSh/FRLG; Bluetooth.

## Aceite da v1

No celular do dono, só com o APK do Release:
- instalar;
- escolher o `prod.keys`;
- "Preparar placa" numa ESP32 recém-apagada;
- "Baixar eventos";
- distribuir um evento SwSh a um Sword e um `.pk3` a um FireRed;
- Parar/Pausar funcionando;
- o aviso de versão nova aparecendo.

Os testes do desktop seguem verdes, sem mudança de comportamento no `.exe`.
