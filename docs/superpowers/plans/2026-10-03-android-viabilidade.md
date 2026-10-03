# Distribuidor no Android: prova de viabilidade

> **Estado:** ideia registrada, execução adiada (2026-10-03). Ainda não há decisão de construir o app. Este plano só responde: *dá para rodar o Distribuidor num celular Android com a ESP32 no USB (OTG)?*

**Objetivo:** provar ou derrubar, com o menor esforço possível, as 3 premissas de que um APK depende. Se as 3 passarem, escrever spec e plano do app (Flet `flet build apk`, reaproveitando `distrib/` e `ui/`).

**Arquitetura-alvo (se der certo):** APK Flet + ESP32 no USB-C via adaptador OTG. A serial vai pela API USB Host do Android, porque sem root não existe `/dev/tty*`. O catálogo de SwSh é validado antes, no PC, e o celular não roda PKHeX. O "Preparar placa" continua no `.exe` do PC.

**Descartados (motivo registrado):**
- **Bluetooth na própria ESP32:** o rádio é um só, dividido entre Wi-Fi e BT. O host precisa de resposta rápida (já houve o `no reply 0x81`) e de cerca de 90 KB/s contínuos (921600 baud). Também exigiria um fork do firmware do autor. Alternativa possível no futuro: uma 2ª placa (ESP32-C3) como ponte BT↔UART por fio.
- **Site/PWA:** o WebUSB funciona no Chrome Android, mas o host inteiro (trio, pycryptodome, unicorn) teria que rodar em WASM ou ser reescrito em JS.
- **iPhone:** não tem serial USB. Fora de escopo.

**Fatos do código (pokeldn v0.5.0, `vendor/pokeldn`):**
- Serial aberta em `pokeldn/ldn/esp32.py:279` (`serial.Serial()`). O baud padrão é 921600 (`pokeldn/app/settings.py:19`), e o env `POKELDN_ESP32_BAUD` sobrescreve.
- Dependências nativas: `pycryptodome`, `zstandard`, `unicorn==2.1.4`. O `trio` e o `pyserial` são Python puro.
- O `unicorn` é usado em `bin/swsh_gift_host.py:60` (`validate`, a checagem NSO, que exige a imagem do jogo e é **opcional** pelo `--help`, linha 114), em `pokeldn/frlg/gift/mg_client.py` e em `pokeldn/frlg/rom/buffer_script.py` (o FRLG **depende** dele).
- A validação PKHeX é **obrigatória** no presente do SwSh. O serviço .NET fica em `vendor/pokeldn/services/pkhex/` (`Program.cs`).
- No distrib, o HELLO e o "aquietar" ficam em `distrib/runners/quiet.py` (`quiet_info`, `quiet`) e em `distrib/runners/hello.py`.

**Material necessário:** celular Android com USB-C (Android 8 ou mais novo, de preferência ARM64), adaptador/cabo OTG USB-C → micro-USB ou USB-C (conforme a placa), a ESP32 Nerdsking já com o firmware v0.5.0, o PC com o repo e o Switch com o Sword (só no passo 4).

---

## Passo 1: o celular reconhece e alimenta a placa (manual, cerca de 15 min)

1. Instalar o app **"Serial USB Terminal"** (Kai Morich, Play Store), que usa a biblioteca `usb-serial-for-android`.
2. Ligar a ESP32 no celular pelo OTG e aceitar a permissão USB.
   - Esperado: o app lista o dispositivo como **CDC** (CH9102, VID `1a86`).
   - Se não aparecer, testar outro cabo ou adaptador. Se o LED da placa nem acender, o celular não fornece energia pelo OTG (ver *Bloqueadores*).
3. Configurar 921600 baud, 8N1, e conectar. O firmware v0.5.0 fala binário, então esperar só bytes "sujos" ou nada. O passo só confere que a porta abre e se mantém aberta por 1 minuto.

**Aceite:** a porta abre a 921600 e a placa continua ligada. **Se falhar:** testar um hub OTG com energia externa. Se ainda falhar, encerrar a prova (premissa 1 derrubada).

## Passo 2: host Python no celular via Termux (cerca de 1 sessão)

O Termux é o jeito mais barato de rodar o host Python no Android antes de pensar em APK.

1. Instalar o **Termux** e o **Termux:API** pelo F-Droid (a versão da Play Store é velha). No Termux: `pkg install python clang make cmake rust libusb termux-api git`.
2. `pip install pycryptodome zstandard trio pyserial pyusb`. Depois `pip install unicorn==2.1.4`, que compila do código-fonte (lento; anotar o tempo e qualquer erro).
   - **Aceite parcial:** `python -c "import Crypto, zstandard, trio, unicorn; print('ok')"` imprime `ok`.
3. Acesso USB sem root: `termux-usb -l` lista o dispositivo, e `termux-usb -r -e python3 script.py /dev/bus/usb/XXX/YYY` entrega um **file descriptor** ao script.
   - Escrever `android_spike/usb_fd_serial.py`: uma classe com a mesma interface usada pelo `esp32.py` (`open`, `read`, `write`, `timeout`, `close`, `in_waiting`), implementada com `pyusb` + `libusb` a partir do fd (`libusb_wrap_sys_device`). Configurar CDC-ACM com `SET_LINE_CODING` a 921600 8N1 e `SET_CONTROL_LINE_STATE` com DTR/RTS **desligados**, para não resetar a ESP32.
   - Para injetar a classe, fazer um monkeypatch de `serial.Serial` antes de importar `pokeldn.ldn.esp32`.
4. Clonar o repo no Termux e rodar o equivalente ao HELLO com quiet: `distrib/runners/hello.py`, com a porta substituída pelo fd.

**Aceite:** o HELLO responde com a info do firmware (a mesma string que o `.exe` mostra no cartão da placa). **Se o `unicorn` não compilar:** anotar e seguir. O SwSh sem a checagem NSO não precisa dele, e o FRLG fica pendente, como já está no Windows.

## Passo 3: catálogo SwSh pré-validado no PC (cerca de meia sessão, executável por Sonnet)

Assim o celular não precisa rodar PKHeX (.NET).

1. No PC, script `build/prevalidate_swsh.py`: para cada `.wc8` do catálogo, roda a mesma validação PKHeX que o `swsh_gift_host.py` exige e grava `catalog/swsh_validated.json` com `{arquivo: sha256, ok: bool, motivo}`.
2. Adicionar a `swsh_gift_host` (via runner do distrib, **sem alterar o vendor**) um caminho "validado previamente": se o sha256 do `.wc8` consta como `ok` no JSON, a chamada ao PKHeX é pulada. Antes, conferir em `bin/swsh_gift_host.py` se dá para pular o PKHeX por flag ou com um stub do serviço. Se não der sem tocar no vendor, o caminho é um **stub do serviço PKHeX** que responde a partir do JSON.
3. Testes: um teste unitário para o lookup (sha presente/ausente/`ok=false` → recusa).

**Aceite:** no PC, com o serviço PKHeX desligado, um presente SwSh do JSON é aceito e um fora dele é recusado. `pytest` verde.

## Passo 4: Mystery Gift real pelo celular (manual, com o Switch)

1. No Termux, com `prod.keys` copiado para o celular, rodar o host SwSh (com quiet antes) usando o adaptador do passo 2 e o catálogo do passo 3. Usar o Zarude, como na Task 2 do plano do `.exe`.

**Aceite:** o Zarude chega no Sword. Gravar o log em `tests/fixtures/logs/android_swsh_spike.txt` (UTF-8).

## Veredito e próximo passo

- **3 premissas ok (passos 1, 2 e 4):** escrever a spec do APK. Pontos dela: Flet mobile (`flet build apk`), a serial via plugin Flutter `usb_serial` ou via `pyjnius`/Android USB API em vez do Termux, o empacotamento das dependências nativas para arm64 (verificar o índice de pacotes mobile do Flet e, se faltar, receita própria para `unicorn`), as permissões USB no manifest e o `prod.keys` pelo seletor de arquivos.
- **Alguma falhou:** registrar o motivo aqui e no vault e encerrar a ideia, ou reavaliar a ponte Bluetooth com a 2ª placa.

## Bloqueadores conhecidos

- **Energia:** alguns celulares fornecem pouca corrente pelo OTG. A ESP32 em TX pede até cerca de 250 mA de pico. Contorno: hub OTG com energia.
- **DTR/RTS:** abrir a porta com DTR/RTS ligados reseta a ESP32 (esse é o auto-reset do esptool). No adaptador eles precisam ficar desligados.
- **Licença:** o pokeldn é AGPL-3.0. Um APK que embute o pokeldn precisa publicar o código-fonte, como já se faz no `.exe`.
