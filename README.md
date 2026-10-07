<div align="center">

<img src="ui/assets/pokeball.svg" width="96" alt="Pokébola">

# Distribuidor de Eventos

**Eventos de Mystery Gift no seu Switch e no seu GBA, com uma placa ESP32 de poucos reais.**

[![Última versão](https://img.shields.io/github/v/release/Carlos-Gabryel/pokeldn-distrib?label=vers%C3%A3o&color=e3350d)](https://github.com/Carlos-Gabryel/pokeldn-distrib/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/Carlos-Gabryel/pokeldn-distrib/total?color=3b4cca)](https://github.com/Carlos-Gabryel/pokeldn-distrib/releases)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078d4?logo=windows)
![Android](https://img.shields.io/badge/Android-arm64-3ddc84?logo=android&logoColor=white)
[![Licença MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-ffcb05)](LICENSE)

[**⬇ Baixar para Windows**](https://github.com/Carlos-Gabryel/pokeldn-distrib/releases/latest/download/Distribuidor.exe) ·
[**⬇ Baixar para Android**](https://github.com/Carlos-Gabryel/pokeldn-distrib/releases/latest/download/Distribuidor.apk)

</div>

---

O Distribuidor transforma uma placa **ESP32** num ponto de distribuição de eventos, como os
que existiam nas lojas. Você escolhe o Pokémon numa lista com sprites, aperta **Distribuir** e
os consoles por perto recebem o presente pela comunicação local. Por baixo, ele usa o
[pokeldn](https://github.com/Decryptu/pokeldn), com uma interface feita para quem não quer
abrir terminal.

## ✨ O que ele faz

|  | Sword / Shield | FireRed / LeafGreen |
|---|---|---|
| **Como chega** | Presente Misterioso por comunicação local | Mystery Gift → Wonder Card |
| **Consoles ao mesmo tempo** | Vários | Um por vez |
| **Eventos** | Catálogo do Events Gallery, validados pelo PKHeX | Wonder Cards oficiais, com rodízio de PID |
| **Windows** | ✅ | ✅ |
| **Android** | ✅ (só os eventos pré-validados) | ✅ |

- **Tudo num programa só:** sem instalação, sem WSL, sem Python e sem .NET.
- **Catálogo com busca:** Pokémon com sprite, nome e eventos disponíveis para cada jogo.
- **Painel ao vivo:** console conectado, quantos presentes saíram, há quanto tempo está no ar e o último resultado.
- **Prepara a placa sozinho:** grava o firmware do pokeldn na ESP32 com um clique.
- **Atualiza sozinho:** avisa quando sai versão nova.

## 🧰 Do que você precisa

| Item | Detalhes |
|---|---|
| **Placa ESP32** | ESP32 clássica, ESP32‑S3, ESP32‑C3 ou ESP32‑C6. As DevKit comuns servem. |
| **Cabo USB de dados** | Cabo só de carga não funciona. No Android, use também um adaptador **OTG**. |
| **`prod.keys`** | Extraído **do seu próprio Switch** (por exemplo, com o Lockpick_RCM). Não é distribuído aqui. |
| **Um computador ou celular** | Windows 10/11 x64 ou Android arm64. |

## 🚀 Primeiros passos no Windows

1. **Baixe** o [`Distribuidor.exe`](https://github.com/Carlos-Gabryel/pokeldn-distrib/releases/latest/download/Distribuidor.exe) e abra.
   > Se aparecer *"O Windows protegeu o computador"*, clique em **Mais informações → Executar assim mesmo**. O programa não tem assinatura digital, que é paga.
2. **Configuração inicial**, feita uma vez só, em três passos:
   1. **Escolher prod.keys:** aponte para o arquivo extraído do seu Switch.
   2. **Baixar eventos:** baixa o catálogo de eventos.
   3. **Placa:** plugue a ESP32. Se ela for nova, abra a aba **Placa → Preparar placa → Gravar**.
3. **Distribua:** **Distribuir → jogo → Pokémon → evento → Distribuir.**

Seus dados ficam em `%LOCALAPPDATA%\Distribuidor`.

### No console

<table>
<tr><th>Sword / Shield</th><th>FireRed / LeafGreen</th></tr>
<tr><td>

1. Menu **X → Presente Misterioso**
2. **Receber presente**
3. **Por comunicação local**
4. Espere o presente aparecer e aceite

Vários Switches podem receber ao mesmo tempo.

</td><td>

1. Na tela inicial, **MYSTERY GIFT**
2. **WONDER CARDS → FRIEND**
3. Aguarde a conexão

Um console por vez. Use **Pausar**, **Retomar** e **Parar** entre um e outro.

</td></tr>
</table>

## 📱 Android

O mesmo app roda no celular, com a placa ligada pelo USB‑C através de um adaptador OTG. Não precisa de root.

1. Baixe o [`Distribuidor.apk`](https://github.com/Carlos-Gabryel/pokeldn-distrib/releases/latest/download/Distribuidor.apk) no celular e abra.
2. Permita a instalação de **fontes desconhecidas** para o app que abriu o arquivo (o navegador ou o gerenciador de arquivos).
3. Ligue a placa pelo OTG e aceite a permissão de USB.
4. Siga as mesmas telas do PC: **Preparar placa**, **Baixar eventos** e **Distribuir**.

> **Por que aparecem menos eventos de Sword/Shield?** O PKHeX não roda no celular. Por isso o app
> usa um catálogo validado antes no PC (`swsh_validated.json`, que ele baixa sozinho da última
> versão) e mostra só os eventos aprovados.

Para atualizar, instale o `.apk` novo por cima. Os dados e o `prod.keys` continuam no celular.

## 🛠️ Problemas comuns

<details>
<summary><b>A placa está plugada, mas não aparece</b></summary>

- Instale o driver do chip USB da placa. O nome vem escrito perto do conector: **CP2102**
  ([driver](https://www.silabs.com/developer-tools/usb-to-uart-bridge-vcp-drivers)) ou
  **CH340 / CH9102** ([driver](https://www.wch-ic.com/downloads/CH341SER_EXE.html)).
- Troque o cabo. Muitos cabos só carregam e não transmitem dados.
- Replugue a placa e clique em **Testar de novo**.
</details>

<details>
<summary><b>A placa não responde ou dá erro ao distribuir</b></summary>

Abra **Placa → Preparar placa** e grave o firmware de novo. Isso apaga o que estava na placa,
mas não estraga nada.
</details>

<details>
<summary><b>No Android, a placa não acende ou fica reiniciando</b></summary>

Alguns celulares não fornecem energia suficiente pelo OTG. Coloque um **hub USB com fonte
própria** entre o celular e a placa.
</details>

<details>
<summary><b>O Switch não encontra o presente</b></summary>

- Confira se o Distribuidor está **no ar**: o painel mostra o tempo correndo.
- Deixe o console perto da placa, a menos de 1 ou 2 metros.
- No Sword/Shield, escolha **Por comunicação local**, e não "Pela internet".
</details>

## 👩‍💻 Desenvolvimento

Requer Python 3.14 e, para gerar o `.exe`, o .NET SDK.

```bash
git clone --recurse-submodules https://github.com/Carlos-Gabryel/pokeldn-distrib
cd pokeldn-distrib
py -3.14 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt

.venv/Scripts/python.exe -m pytest -q     # testes
.venv/Scripts/python.exe main.py          # roda o app

.venv/Scripts/python.exe build/fetch_firmware.py
.venv/Scripts/python.exe build/pack.py    # gera dist/Distribuidor.exe (com PKHeX embutido)
```

O APK é gerado só no GitHub Actions (`.github/workflows/android-app.yml`, via
`build/pack_android.py`), porque o `flet build` no Windows exige symlinks.

<details>
<summary>Estrutura do projeto</summary>

```
distrib/     núcleo: catálogo, placa, rádio, distribuição e atualização
  games/     um adaptador por jogo (swsh, frlg)
  runners/   processos que conversam com a placa
ui/          interface Flet (início, distribuir, placa, ajustes)
build/       empacotamento (.exe e .apk), firmwares e ícones
vendor/      pokeldn (submódulo)
tests/       pytest
```
</details>

## 📜 Licença e créditos

O código deste repositório é [MIT](LICENSE). O `.exe` inclui o
[pokeldn](https://github.com/Decryptu/pokeldn) e os firmwares dele, sem modificação, sob a
licença do autor (AGPL‑3.0).

- **Eventos:** [Events Gallery](https://github.com/projectpokemon/EventsGallery), do Project Pokémon
- **Validação:** [PKHeX](https://github.com/kwsch/PKHeX)
- **Sprites e nomes:** [PokeAPI](https://pokeapi.co)
- **Ícones:** [Lucide](https://lucide.dev) (ISC)

<sub>Pokémon e todos os nomes relacionados são marcas da Nintendo, Game Freak e The Pokémon Company.
Este é um projeto de fãs, sem fins lucrativos e sem afiliação com elas. Use somente com jogos e
consoles que você possui.</sub>
