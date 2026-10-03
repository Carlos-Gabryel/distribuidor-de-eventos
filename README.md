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
