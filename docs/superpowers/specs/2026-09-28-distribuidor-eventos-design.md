# Distribuidor de Eventos (pokeldn-distrib): design

- **Data:** 2026-09-28
- **Status:** aprovado em conversa, aguardando revisão deste documento
- **Depende de:** [pokeldn](https://github.com/Decryptu/pokeldn), fixado no commit `89f761e`, que não é modificado

## 1. Objetivo

Uma ferramenta de terminal para **distribuir Pokémon de evento que não podem mais ser recebidos**
em encontros de Pokémon. Roda num notebook Windows com uma ESP32 no USB; quem recebe são os
consoles (Switch 1 ou 2, sem modificação) de outras pessoas.

**Sucesso =** no evento, o operador liga o notebook, abre o atalho e escolhe o jogo e o evento
(ex.: "Sword/Shield → Jungle Zarude" ou "FireRed → 10ANIV Lugia"). A distribuição fica no ar sem
nenhum comando digitado, sem saber de `/dev/ttyACM0`, de root ou de flags do pokeldn.

**Jogos:** os dois que têm Mystery Gift por comunicação local no pokeldn:
- **Sword/Shield (SwSh)**
- **FireRed/LeafGreen (FRLG)** (o dono tem FireRed para os testes reais)

**Fora de escopo (v1):** trocas, montar Pokémon do zero, rotação automática de eventos,
sprites/imagens, ovos de evento da Gen 3, instalação 100% automática do WSL.

## 2. Decisões tomadas

| Decisão | Escolha | Por quê |
|---|---|---|
| Interface | TUI com busca (biblioteca **Textual**) | 925 + ~3.180 eventos exigem busca; roda no terminal; menos peças que uma página web |
| Modo de distribuição | **Vitrine**: um evento fica no ar até o operador trocar | É como as distribuições oficiais; o operador só troca quando quer |
| Onde fica o código | Projeto separado, que usa o pokeldn como dependência | O pokeldn é de terceiros (AGPLv3); não modificamos o repo dele |
| Catálogo | Baixado do **Events Gallery do Project Pokémon** antes do evento e guardado offline | Pode não haver internet no local do evento |
| Firmware da placa | Gravado uma vez em casa; o notebook não precisa do ESP-IDF | Menos coisa para instalar no notebook |
| Versão do pokeldn | Fixada em `89f761e` | Uma atualização do autor não pode quebrar a ferramenta às vésperas de um evento |

## 3. Como cada jogo distribui (fatos do pokeldn)

### 3.1 Sword/Shield: anúncio, vários consoles de uma vez

- `bin/swsh_gift_host.py --record CARD.wc8` anuncia uma rede LDN cujo `app_data` (0x180 bytes)
  carrega o Wonder Card em fragmentos (720 bytes = 3 fragmentos). **O console não se conecta:**
  a tela "Receber presente → Por comunicação local" só escaneia e lê o cartão do anúncio.
- Consequências: **vários consoles recebem ao mesmo tempo**; **não dá para contar entregas**;
  o próprio jogo recusa um cartão que aquele save já recebeu.
- Validado em 2026-09-28: um Wonder Card montado pelo pokeldn (Pikachu) chegou a um Sword
  num Switch 2.
- Precisa de **root** (o host cria uma interface TAP) e da porta explícita
  (`POKELDN_RADIO=esp32:/dev/ttyACM0`; o `esp32:auto` só procura `ttyUSB*`).
- O validador do jogo (`--image main.bin`) exige o executável do Sword, que não temos; usamos
  `--no-validate` e verificamos o checksum do cartão nós mesmos (`pokeldn.swsh.wc8.sealed`).

### 3.2 FireRed/LeafGreen: sessão, um console por vez

- O console escolhe o host em "Mystery Gift → Wonder Cards → Friend" e **entra na sessão**.
  O host envia um script; o console executa. **Uma pessoa por vez**, e o host é reiniciado
  entre consoles (`docs/frlg_gift.md`, "Serving consoles back to back: not built").
- Para entregar um **Pokémon de evento histórico**, usamos o comando `givepokemon` do Mystery
  Event: ele copia uma `struct Pokemon` completa (100 bytes, criptografada, com checksum) para a
  equipe e marca a Pokédex (`pokeldn.frlg.rom.mystery_event`, `pokeldn.frlg.save.mevent_pokemon`).
  O Pokémon chega com o **OT, o ID e o PID originais** do evento, direto na equipe.
- **Equipe cheia:** o console recusa e devolve status 3. O host lê esse status, então dá para
  avisar "equipe cheia".
- Os presentes que o autor já montou (`--gift altering-cave`, `battle-count-card` etc.) entram
  como **extras**.
- **Risco:** nunca testado com um `.pk3` de fora (o autor só entregou Pokémon montados por ele).
  O plano começa por uma prova de conceito no FireRed do dono (seção 9).

## 4. Arquitetura

```
Windows                                  WSL2 (Ubuntu), como root
┌──────────────────────────────┐         ┌──────────────────────────────────────────────┐
│ Iniciar Distribuicao.bat      │ ──────▶ │ python -m distrib  (TUI Textual)              │
│  - garante o WSL rodando      │         │   ├─ games/swsh.py  ─┐                         │
│  - acha a ESP32 (VID:PID)     │         │   ├─ games/frlg.py  ─┼─ catalog.py (índice)    │
│  - usbipd attach              │         │   └─ distributor.py ─┘   radio.py (porta/HELLO)│
│  - wsl -u root → TUI          │         │         │ subprocesso                          │
└──────────────────────────────┘         │         ▼                                      │
                                         │  SwSh: pokeldn/bin/swsh_gift_host.py --record   │
                                         │  FRLG: distrib/runners/frlg_session.py (nosso,  │
                                         │        importa o pokeldn como biblioteca)       │
                                         └──────────────────────────────────────────────┘
```

### 4.1 Unidades

| Unidade | Faz | Depende de |
|---|---|---|
| `Iniciar Distribuicao.bat` | Prepara o Windows (WSL, `usbipd attach`) e abre a TUI como root. Mensagens em português se a placa faltar ou se o `bind` não tiver sido feito | `usbipd`, `wsl` |
| `distrib/config.py` | Lê `config.toml` (+ `config.local.toml`): caminho do pokeldn, do Python do venv e do `prod.keys` | — |
| `distrib/radio.py` | Acha a porta serial (`/dev/ttyACM*`, `/dev/ttyUSB*`) e faz o HELLO para confirmar a placa e o firmware | pokeldn (`esp32_wlan`) |
| `distrib/catalog.py` | Modelo comum: `Event` (id, jogo, nome, tipo, detalhes, variantes, válido?) e o índice salvo em JSON. Busca, filtros, favoritos | — |
| `distrib/games/base.py` | Contrato de um jogo: `load_catalog()`, `build_job(event, variant) → comando`, `parse_line(linha) → estado` e `mode` (`broadcast` ou `session`) | `catalog` |
| `distrib/games/swsh.py` | Lê `.wc8` (um evento por arquivo) e monta o comando do `swsh_gift_host.py` | pokeldn (`swsh.wc8`) |
| `distrib/games/frlg.py` | Lê `.pk3` (80 ou 100 bytes), agrupa por evento, faz o rodízio de PIDs e inclui os extras do autor | pokeldn (`frlg.save.mon`, `mevent_pokemon`) |
| `distrib/runners/frlg_session.py` | **Nosso host de uma sessão FRLG:** recebe um `.pk3` (ou o nome de um extra), monta um `WonderGift` com `givepokemon`, serve **um** console e termina imprimindo uma linha `RESULT {json}` (entregue / equipe cheia / erro) | pokeldn (`frlg.gift.*`, `ldn`) |
| `distrib/distributor.py` | Supervisor de processo: inicia/para o host, lê a saída linha a linha, expõe o estado (`subindo`, `no ar`, `console conectado`, `entregue`, `erro`), reinicia após queda (até 3 falhas seguidas) e, no FRLG, reinicia após cada console. Nada de interface | `games/*` |
| `distrib/app.py` | Telas Textual. Só fala com `catalog`, `distributor` e `radio` | Textual |
| `distrib/__main__.py` | `python -m distrib` (TUI) e `python -m distrib atualizar-catalogo [swsh\|frlg]` | tudo acima |
| `instalar.ps1` | Instalação no notebook (seção 8) | `winget`, `wsl` |

Cada jogo é um adaptador do mesmo contrato, então as telas não sabem se o jogo é "broadcast"
(SwSh) ou "session" (FRLG); só mostram o estado que o `distributor` informa.

### 4.2 Layout do repositório

```
pokeldn-distrib/
  Iniciar Distribuicao.bat
  instalar.ps1
  config.toml                 # padrões versionados
  config.local.toml           # por máquina (ignorado pelo git)
  distrib/  (código acima)
  tests/    (pytest + fixtures pequenas: alguns .wc8 e .pk3 reais)
  catalog/  (ignorado pelo git; gerado pelo atualizar-catalogo)
    swsh/*.wc8, swsh/index.json
    frlg/*.pk3, frlg/index.json
  state/    (ignorado: favoritos.json, rodizio_pid.json)
  logs/     (ignorado: AAAA-MM-DD.log)
  docs/     (specs, planos, guia de instalação)
```

## 5. Catálogo

### 5.1 Sword/Shield

- **Fonte:** `Released/Gen 8/SwSh/Wondercards/*.wc8` no GitHub `projectpokemon/EventsGallery`
  (925 arquivos em 2026-09-28). Fora: "Wild Area Events" (não são presentes) e "HOME Simulated WCs".
- **Uma entrada por arquivo.** Cada `.wc8` do Events Gallery já é um evento completo, e as
  versões regionais vêm em arquivos separados ("Jungle Zarude (Japanese Release)",
  "(Western Release)", "(Korean Release)"). **Não agrupar pelo ID do cartão:** o ID não é
  único (o `0001` aparece em 134 cartões de competição diferentes). Os 925 incluem as
  subpastas "Ranked Battles" (700) e "Online Competition" (64), quase só BP e itens, que o
  filtro "só Pokémon" esconde.
- **Sem configuração de idioma:** a região faz parte do nome do evento, e o operador escolhe
  a versão que quer. (Verificado em 2026-09-28: o `.wc8` do "Jungle Zarude (Western Release)"
  vem com 720 bytes e **já selado**.)
- **Campos lidos com `pokeldn.swsh.wc8.read(rec)`**, que devolve um dict: `kind` (1 = Pokémon),
  `species`, `form`, `level`, `shiny_type`, `gigantamax`, `ball`, `held_item`, `tid`/`sid`, `ot`,
  `card_id`, `region_mask` (máscara de versão: 1 Sword, 2 Shield, 3 ambos) e `sealed`. O nome
  vem do arquivo, sem o prefixo numérico e o "SWSH -"/"SW -"/"SH -".
- **Validade:** `wc8.sealed(rec)`; se o checksum não bater, re-sela na importação
  (`wc8.seal`); se o tamanho não for 720, marca inválido e esconde.

### 5.2 FireRed/LeafGreen

- **Fonte:** os `.pk3` em `Released/Gen 3/**` do mesmo repositório (~3.180 arquivos em
  2026-09-28, ENG e JPN). Fora: `.raw`, `.ect`, `.ecb`, `.me3`, `.wc3`, `.sav` (e-Reader e
  cartões de Emerald/RS, que não passam por esta rota).
- **Uma entrada por evento:** agrupa pela **pasta + nome do arquivo sem a etiqueta de PID**
  (ex.: `RSEFL - WISHMKR Jirachi (1910) (ENG).pk3` e `(4CB7)` viram o evento "WISHMKR Jirachi
  (ENG)"; na pasta "Top 10 Distribution", cada espécie é um evento). Cada arquivo é uma
  **variante de PID**.
- **Rodízio de PID:** cada entrega usa a próxima variante do evento, como nas distribuições
  originais. O contador fica em `state/rodizio_pid.json`.
- **Campos lidos com `pokeldn.frlg.save.mon.Mon.from_file(path).decode()`:** espécie, nível,
  shiny (calculado de PID/TID/SID), OT, TID, item, golpes, idioma e se é ovo. **Ovos ficam fora
  na v1.** A espécie é o **índice interno da Gen 3**, não o número da Pokédex nacional (Hoenn
  vai de 277 a 411; o Jirachi é 409), então a validação é "espécie presente em
  `pokeldn.frlg.save.basestats.BASE_STATS`" + checksum OK. (Verificado em 2026-09-28 com o
  Lugia 10ANIV e o Jirachi WISHMKR: checksum OK, OT e nível corretos.)
- **Conversão:** `Mon.from_pk3` já faz tudo: 80 → 100 bytes, cauda de party com stats,
  criptografia e o byte de mail = `0xFF`. `mevent_pokemon.build_givepokemon_payload(mon)`
  acrescenta a `struct Mail` vazia.
- **Extras:** entradas fixas para os presentes do autor que fazem sentido num evento:
  `altering-cave`, `battle-count-card`, `beast-cutscene-share`, `celebi`, `porygon-tm-gift`,
  `solrock-stamp`, `lunatone-stamp`, `master-ball`, `worlds-xp` e `visiting-trainer` (só
  FireRed). As sondas de pesquisa (`rng-*`, `mystery-event-probe`, `resident-*`, `save-loader`,
  `mevent-opcode-sweep`) ficam de fora.

### 5.3 Comum

- `python -m distrib atualizar-catalogo` baixa pelo GitHub (tarball do repositório, uma única
  requisição) e gera `index.json`. Roda em casa, com internet; o evento funciona offline.
- **Busca** por texto no nome, espécie e OT. **Filtro padrão:** só Pokémon (SwSh: itens, roupas
  e BP aparecem com uma tecla). **Ordenação:** pelo número do cartão (SwSh) ou pelo nome do
  evento (FRLG).
- **Vitrine do dia (favoritos):** `F` marca ou desmarca; os favoritos aparecem no topo.
  Salvo em `state/favoritos.json`.

## 6. Telas e fluxo

1. **Checagem** (ao abrir): placa encontrada + HELLO (porta e versão do firmware), `prod.keys`
   presente, catálogos (quantos eventos por jogo). Cada item com ✓/✗ e a ação em português
   ("Plugue a placa e aperte R").
2. **Jogo:** Sword/Shield · FireRed/LeafGreen.
3. **Catálogo:** busca no topo, a vitrine do dia e a lista à esquerda, os detalhes à direita.
   `Enter` distribuir · `F` vitrine · `I` itens/roupas/BP (SwSh) · `Esc` voltar.
4. **No ar:**
   - **SwSh:** "● NO AR há mm:ss", evento, canal, reinícios e a instrução para os
     jogadores (Presente Misterioso → Receber presente → Por comunicação local).
   - **FRLG:** "● AGUARDANDO CONSOLE" / "CONSOLE CONECTADO" / "✓ ENTREGUE" (com o PID
     usado), **contador de entregas** e o último "equipe cheia"; volta sozinho para
     "aguardando". A instrução: Mystery Gift → Wonder Cards → Friend.
   - `T` trocar evento (o atual continua no ar até escolher outro; a troca leva ~5–10 s)
     · `P` pausar · `Q` sair.

## 7. Tratamento de erros

| Situação | Comportamento |
|---|---|
| Placa não plugada, ou `bind` não feito | O `.bat` avisa antes da TUI, com o comando exato |
| Placa desplugada no meio | "⚠ placa desconectada"; a TUI fica tentando achar a porta e volta a distribuir quando ela reaparece. O attach do Windows é refeito pelo `.bat` num laço de fundo enquanto a TUI está aberta |
| Host cai | Reinicia; depois de **3 falhas seguidas** para e mostra o erro com a última linha do log |
| FRLG: equipe cheia | Mostra "equipe cheia: peça para liberar um espaço na equipe" e continua aguardando |
| FRLG: console travado / sessão sem resposta | Tempo limite por sessão (padrão 120 s) → reinicia o host |
| `.wc8`/`.pk3` inválido | Re-selado se possível; senão escondido e contado em "inválidos" na checagem |
| Sem `prod.keys` / catálogo vazio | A tela de checagem aponta o que falta |

Toda a saída dos hosts vai para `logs/AAAA-MM-DD.log`.

## 8. Instalação no notebook

- **Pré-requisito manual** (guia `docs/instalacao.md`, passo a passo): `wsl --install -d Ubuntu-24.04`
  (pode pedir reinício) e copiar o `prod.keys` para `~/.switch/prod.keys` no WSL.
- **`instalar.ps1`** (admin, com internet, em casa): instala o `usbipd-win` via `winget`; no WSL,
  instala `git` e `python3-venv`, clona o pokeldn e fixa `89f761e` com `core.autocrlf=false`,
  cria o venv e instala o `requirements.txt` do pokeldn e o Textual; baixa os catálogos; faz o
  `usbipd bind` da placa plugada; cria o atalho na área de trabalho.
- A placa já vai gravada com o firmware do pokeldn (feito em casa, neste PC).

## 9. Testes

### 9.1 Automáticos (pytest, sem placa)

- **Catálogo SwSh:** leitura dos campos em `.wc8` reais de fixture, nome limpo a partir do arquivo,
  re-selagem, filtros e busca.
- **Catálogo FRLG:** leitura de `.pk3` de 80 e 100 bytes, conversão box → party (conferida
  decodificando de volta com `pokeldn.frlg.save.mon.decode_mon`), rodízio de PID, exclusão de ovos.
- **Distributor:** com um **host falso** (script que imprime as linhas reais de cada estado,
  cai ou trava), cobre subir/no ar, reinício após queda, limite de 3 falhas, ciclo por console no
  FRLG e tempo limite.
- **TUI:** o `Pilot` da Textual cobre buscar, favoritar, distribuir, trocar e pausar, com o
  distributor falso.
- **Runner FRLG offline:** o pokeldn tem um modelo do cliente do console
  (`pokeldn.frlg.gift.mg_client`, usado por `tests/test_mystery_gift_flow.py`; o harness citado na
  doc, `scratchpad/mg_client_harness.py`, não vem no repo). O script gerado pelo runner passa por
  ele e pela validação do `GIFT_REGISTRY.register_definition` antes de qualquer teste com console.

### 9.2 Reais (placa + consoles do dono), nesta ordem

1. **Prova de conceito FRLG (bloqueante para a parte FRLG):** um `.pk3` 10ANIV do Events
   Gallery chega na equipe do FireRed, com OT/ID/PID corretos no resumo.
2. **SwSh com cartão do Events Gallery:** um `.wc8` baixado (não montado por nós) chega no Sword.
3. **Regiões SwSh:** um cartão "Japanese Release" e um "Western Release" no Sword do dono.
4. **FRLG equipe cheia:** a mensagem aparece e a próxima tentativa funciona.
5. **Trocar de evento** com o anúncio no ar (SwSh) e entre consoles (FRLG).
6. **Desplugar/replugar** a placa com o anúncio no ar.
7. **Ensaio geral no notebook,** com a internet desligada, a partir do atalho.

## 10. Riscos e perguntas em aberto

- **FRLG com `.pk3` de fora** (seção 3.2): se a prova de conceito falhar, a parte FRLG da v1
  fica só com os extras do autor, e o motivo é registrado.
- **Cartão de outra região** num Sword de outro idioma: provavelmente aceito (cartões
  multilíngues), confirmado no teste 9.2.3.
- **Checksum dos `.wc8`:** o que testamos veio selado; a re-selagem na importação cobre algum
  que não venha.
- **Legalidade da origem dos dados:** os arquivos são as distribuições oficiais arquivadas pela
  comunidade. A ferramenta não altera os dados dos Pokémon (só a selagem/criptografia que o
  transporte exige).
