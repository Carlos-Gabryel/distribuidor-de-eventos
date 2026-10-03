# Distribuidor de Eventos — `.exe` nativo do Windows com interface Flet

Data: 2026-10-03 · Estado: aprovado no brainstorm, aguardando revisão da spec escrita.
Substitui a TUI Textual no WSL descrita em `2026-09-28-distribuidor-eventos-design.md`.

## 1. Objetivo

Quem tem uma placa ESP32 e um Switch baixa **um único `.exe`** do GitHub Releases, dá dois cliques
e distribui eventos de **Mystery Gift** para Pokémon Sword/Shield e FireRed/LeafGreen numa interface
bonita, minimalista e bem estruturada. Sem WSL, sem usbipd, sem root e sem linha de comando em
lugar nenhum. O app se atualiza sozinho.

**Pronto quando:** os 8 testes reais de `docs/testes-reais.md` passam com o `.exe` num PC Windows
**sem WSL**, e uma placa nova é preparada pelo botão "Preparar placa".

## 2. Decisões tomadas

| Tema | Decisão |
|---|---|
| Plataforma | `.exe` nativo do Windows com Flet desktop, empacotado com `flet pack` (PyInstaller), igual ao app do autor |
| Versão atual | **Substituída.** TUI Textual, `instalar.ps1`, `iniciar.ps1`, `usb.ps1` e o atalho WSL saem do repositório quando o `.exe` passar nos testes reais |
| Escopo v1 | Só o que a TUI faz hoje: **Mystery Gift** de SwSh e FRLG (o upstream só tem Mystery Gift nesses dois jogos; os demais só têm Trade). Trade fica para depois |
| Distribuição | Só o `.exe` no GitHub Releases (o aviso do SmartScreen é aceito). Nenhum script de instalação |
| Atualização | Automática pelo GitHub Releases, sem nunca interromper uma distribuição |
| Preparar placa | Sim: o app grava o firmware na placa com `esptool` |
| Código | Escrito do zero. Nada de código ou assets do app do autor; só inspiração de padrões |
| Licença | Nosso código é MIT (commit `ebb4dc1`). O `.exe` inclui o pokeldn (AGPL-3.0) e os firmwares dele; os créditos linkam o código-fonte deles |
| Ano do evento | Não há fonte confiável (o `.wc8` não traz data). No lugar entram os destaques do arquivo ("Shiny · Gigantamax · Nv 60") e a região |

## 3. Arquitetura

```
pokeldn-distrib/
  distrib/              lógica, sem nada de interface
    distributor.py      (fica) laço de hosts, pausa, parada, espera da placa
    catalog.py          (fica) + agrupamento por espécie (ver 5.2)
    games/swsh.py, games/frlg.py, games/base.py   (ficam, adaptados ao pokeldn v0.5.0)
    download.py         (fica) Events Gallery → catálogo em %LOCALAPPDATA%
    config.py           (refeito) caminhos do Windows, sem o "~" do WSL
    radio.py            (refeito) acha a placa por porta COM (serial.tools.list_ports)
    board.py            (novo) chip, ponte USB, driver, gravar firmware (esptool)
    update.py           (novo) consultar Release, baixar, trocar o .exe
    runner.py           (novo) o .exe se reinvoca com --run para rodar hosts e gravação
    service.py          (novo) fachada única que a interface usa (ver 3.1)
    runners/frlg_session.py   (fica, adaptado)
  ui/                   Flet: só tela
    app.py              shell: barra lateral, cartão da placa, navegação, avisos
    theme.py            tokens de cor, tamanhos, componentes base
    views/inicio.py     boas-vindas da primeira abertura
    views/distribuir.py jogo → grade → eventos → distribuindo
    views/placa.py      placa e "Preparar placa"
    views/ajustes.py    prod.keys, catálogo, versão, logs, créditos
    assets/             logo Poké Ball (SVG próprio), ícones Lucide (ISC)
  vendor/pokeldn/       submodule do upstream, fixo na tag v0.5.0 (37410c11e4a48c63c1bdeb3b3e0c55be04e0790d)
  build/                pack.py (flet pack) e o download dos firmwares do Release v0.5.0
  tests/
```

### 3.1 Fronteira entre interface e lógica

A `ui/` só importa `distrib.service.Service`. Nenhuma regra de negócio vive na interface.

`Service` expõe:
- **Estado observável** (um objeto `Snapshot` imutável, publicado a cada mudança):
  `board` (estado da placa + frase acionável), `setup` (keys/catálogo/placa prontos?),
  `run` (parado / iniciando / no ar / pausado / sem placa, evento, entregues, consoles, tempo),
  `log` (últimas linhas), `update` (nenhuma / baixando / pronta).
- **Ações:** `set_keys(path)`, `download_catalog()`, `catalog(game)`, `start(event)`, `pause()`,
  `resume()`, `stop()`, `flash_board()`, `check_update()`, `apply_update()`.

A interface se inscreve com `service.subscribe(callback)` e redesenha pelo `page.run_task` do Flet.
Assim a lógica é testável sem abrir janela e uma futura troca de interface não toca nela.

### 3.2 Processos

- A interface roda no processo principal.
- Hosts do pokeldn (`bin/swsh_gift_host.py`, `bin/frlg_mg_host.py` via `distrib.runners.frlg_session`)
  e a gravação da placa rodam como **processo-filho do próprio `.exe`**: `Distribuidor.exe --run <alvo> <args>`.
  Com Python comum (desenvolvimento), `runner.py` usa `sys.executable` no lugar.
- Processos-filho sem janela (`CREATE_NO_WINDOW`). A saída é lida linha a linha numa thread e vira log.
- Parada: um processo sem janela no Windows não recebe Ctrl+C. O pai **fecha o stdin** do filho; no
  filho, uma thread que lê o stdin chama `_thread.interrupt_main()` no EOF, o que gera o mesmo
  `KeyboardInterrupt` com que os hosts do pokeldn desmontam a rede na placa (mecanismo do upstream,
  reescrito por nós). Sem saída em 15 s → `terminate`; mais 5 s → `kill`. Só vale com
  `DISTRIB_MANAGED_RUN=1` no ambiente do filho.
- A placa é passada como `POKELDN_RADIO=esp32:COMx`.

### 3.3 Dados do usuário

Em `%LOCALAPPDATA%\Distribuidor\` (sobrevivem às atualizações do `.exe`):
`prod.keys`, `config.toml`, `catalog\{swsh,frlg}\` (+ `index.json`), `sprites\` (cache),
`state\` (rodízio de PID do FRLG), `logs\`.

## 4. Visual

- Tema escuro, uma cor de destaque (vermelho Poké Ball `#E8445A`), cantos arredondados,
  botões em pílula, verde/vermelho só para estado.
- Logo: Poké Ball em SVG próprio.
- Ícones: Lucide (licença ISC, permissiva como a MIT), em SVG.
- Fonte padrão do sistema; monoespaçada só no log.
- Referência visual aprovada: mockup `fluxo-v2.html` do brainstorm (4 etapas).

## 5. Telas

### 5.1 Shell
Barra lateral fixa: logo + "Distribuidor", abas **Distribuir**, **Placa**, **Ajustes** e, no rodapé,
o **cartão da placa** sempre visível: ponto verde/vermelho, estado e frase do que fazer
(ex.: "Placa desconectada · Reconecte o cabo USB. A distribuição continua quando ela voltar.").
Faixa discreta no topo quando há atualização pronta.

### 5.2 Distribuir (uma aba que avança por etapas)
Linha de caminho clicável no topo: `Distribuir › Sword / Shield › Zarude › Jungle Zarude`.

1. **Jogo:** dois cartões grandes (SwSh: "925 eventos · vários consoles ao mesmo tempo";
   FRLG: "258 eventos · um console por vez").
2. **Grade de Pokémon:** busca + grade virtualizada (`GridView`), um quadradinho por **espécie**:
   sprite, nome, "N eventos" e os destaques. Itens (SwSh) num quadradinho "Itens"; extras do
   pokeldn (FRLG) num quadradinho "Presentes do pokeldn".
   - Agrupamento: SwSh por `species` do `.wc8`; FRLG pela espécie do `.pk3`. Itens por `kind == "item"`.
3. **Eventos do Pokémon:** sprite grande, nome, lista de eventos com nome, região
   (Ocidente / Japão / idioma do `.pk3`), nível, OT e destaques; botão "Distribuir" em cada um.
4. **Distribuindo:** sprite + nome do evento, "Pausar"/"Continuar" e "Parar", contadores e log ao vivo.
   - SwSh (anúncio): **tempo no ar** e **canal**. O host só anuncia o cartão e não sabe quantos
     consoles o baixaram, então não há "entregues" nem "consoles".
   - FRLG (sessão): **entregues**, **último resultado** (entregue / equipe cheia / não entregue),
     **tempo no ar** e se há um console conectado agora.
   - **Pausar** fica nesta tela. **Parar** encerra e volta para a **grade** do jogo.
   - Trocar de aba durante a distribuição não a interrompe; voltar a "Distribuir" reabre esta etapa.

Enquanto a configuração inicial não está completa, a etapa 1 mostra o que falta e um botão para
resolver, no lugar dos cartões dos jogos.

### 5.3 Primeira abertura
Três passos que ficam verdes quando prontos: **Escolher o `prod.keys`** (copiado para a pasta de
dados), **Baixar os eventos** (barra de progresso) e **Conectar a placa** (com "Preparar placa"
quando ela não tem o firmware). Pode fechar e voltar depois; o estado é recalculado ao abrir.

### 5.4 Placa
Chip, ponte USB, porta COM e firmware. Botão **Preparar placa**: detecta o chip, escolhe
`pokeldn-radio{,-c3,-c6,-s3}.bin`, grava com barra de progresso e termina com o teste de
contato (o atual `radio.py`). Bloqueado durante uma distribuição. Sem nenhuma porta: link do
driver da ponte USB (CP210x, CH340, CH9102), detectada pelo VID:PID.

### 5.5 Ajustes
Trocar `prod.keys`; baixar os eventos de novo; versão + "Procurar atualização"; abrir a pasta
de logs; créditos e licenças (pokeldn AGPL-3.0 com link do código, Events Gallery, sprites do
PokeAPI, set de ícones).

## 6. Atualização automática

- Ao abrir e a cada 6 h: consulta `api.github.com/repos/Carlos-Gabryel/pokeldn-distrib/releases/latest`.
  Versão maior que a atual → baixa o asset `Distribuidor.exe` em segundo plano para a pasta de dados
  e confere o tamanho e o SHA-256 publicado no Release.
- Pronta → faixa "Atualização pronta · Reiniciar". Com distribuição rodando, o botão espera o fim.
  **Nunca reinicia sozinho no meio de uma entrega.**
- Troca: renomeia o `.exe` em uso para `Distribuidor.exe.old`, move o novo para o nome original e
  reabre; a próxima abertura apaga o `.old`. Falha em qualquer passo → desfaz e mantém a versão atual.
- Sem internet → ignora em silêncio.

## 7. Erros

- **Placa:** estados com frase acionável: pronta, desconectada, sem firmware, sem driver,
  ocupada por outro programa, falha no teste de contato. A distribuição espera a placa voltar e
  retoma sozinha (comportamento atual do `distributor.py`).
- **Host:** falha vai para o log; o distribuidor tenta de novo com o limite de falhas atual.
- **Sem internet:** catálogo e sprites do cache; sem sprite → silhueta da Poké Ball.
- **`prod.keys` inválido:** recusado ao escolher, com o motivo.
- **Crash da interface:** stack trace no log, com caminho mostrado na janela de erro.

## 8. Testes

- Os 65 testes atuais, adaptados (COM no lugar de `/dev/tty*`, caminhos do Windows).
- Novos: agrupamento por espécie; `Service` (transições de estado com host falso); `update.py`
  contra um GitHub falso (versão nova, igual, hash errado, falha na troca); `board.py` (escolha do
  firmware por chip, driver por VID:PID); `runner.py` (`--run` em modo fonte).
- A interface não tem teste automatizado de pixel; cada etapa é conferida rodando o app.
- Aceite: os 8 testes reais com o `.exe` num PC sem WSL + "Preparar placa" numa placa apagada.

## 9. Riscos (o plano começa por eles)

1. **Hosts no Windows:** provar que `swsh_gift_host.py` e `frlg_mg_host.py` do v0.5.0 entregam um
   presente no Windows nativo com a camada `userspace`, e que param limpo com Ctrl+C (o mesmo
   `KeyboardInterrupt` que o fechamento do stdin gera).
2. **`frlg_session.py`:** ele registra nosso presente no `GIFT_REGISTRY` antes de montar o parser do
   `frlg_mg_host.py`, que mudou cerca de 180 linhas desde o `89f761e`. Revalidar.
3. **Empacotamento:** `flet pack` com o pokeldn, `vendor/LDN`, `esptool` e os firmwares dentro de um
   `.exe` que se reinvoca com `--run`.
4. **SmartScreen/antivírus:** `.exe` PyInstaller sem assinatura pode ser marcado. Aceito pelo dono;
   documentar no README o "Mais informações → Executar assim mesmo".

## 10. Fora do escopo (v1)

Trade de qualquer jogo; Mystery Gift de outros jogos; ovos de evento da Gen 3; assinatura de código;
macOS/Linux; ano do evento.
