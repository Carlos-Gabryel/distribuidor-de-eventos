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

## Android

O mesmo app roda no celular Android (arm64), com a placa ESP32 ligada por um cabo/adaptador **OTG**.

1. Baixe o `Distribuidor.apk` (artifact `distribuidor-apk` do GitHub Actions ou o Release) e abra no celular.
2. Na primeira vez o Android pede para permitir a instalação de **fontes desconhecidas** para o app que você usou para abrir o arquivo (navegador ou gerenciador de arquivos). Permita e instale.
3. Ligue a placa pelo OTG e aceite a permissão de acesso USB quando o Android perguntar.
4. Se o celular não alimentar a placa (ela não acende ou fica reiniciando), use um **hub USB com energia própria** entre o celular e a placa.

No Android o catálogo mostra só os eventos aprovados pelo PKHeX (validado no PC e embutido no app). O APK só é gerado no GitHub Actions (`.github/workflows/android-app.yml`, via `build/pack_android.py`): o `flet build` no Windows exige symlinks, então não roda na máquina local.

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
