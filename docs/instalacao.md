# Instalação num notebook (ou qualquer PC Windows)

Um script faz tudo. Rode **em casa, com internet** (ou com o hotspot do celular). Depois disso,
no evento, a internet não é necessária.

## O que você precisa

- Windows 10 ou 11.
- A placa ESP32 **já gravada** com o firmware do pokeldn. A gravação é feita uma vez no PC de casa
  (no WSL: `cd pokeldn/firmware/esp32 && idf.py -p /dev/ttyACM0 flash`). O notebook não precisa
  do ESP-IDF.
- Um **cabo USB de dados** (cabos só de carga não funcionam).
- O arquivo `prod.keys` do seu próprio console, num pendrive ou em qualquer pasta do notebook.

## Instalar (uma linha)

1. Plugue a placa (se ela não estiver plugada, tudo bem: o script só avisa).
2. Abra o **PowerShell** (menu Iniciar → digite "PowerShell") e cole:

   ```powershell
   irm https://raw.githubusercontent.com/Carlos-Gabryel/pokeldn-distrib/master/instalar.ps1 | iex
   ```

3. Aceite o pedido de administrador.
4. Quando abrir a janela de arquivo, escolha o seu `prod.keys`.
5. No fim, o script mostra a checagem (✓/✗) e cria o atalho **"Distribuidor de Eventos"** na área
   de trabalho.

Sem PowerShell à mão? Baixe o `instalar.ps1` do repositório e clique com o botão direito →
**Executar com o PowerShell**.

### O que o script faz

1. Instala o WSL e o Ubuntu 24.04 (se faltar) e cria o usuário Linux `distrib` sozinho.
   Se o Windows precisar **reiniciar**, ele pergunta; depois do reinício a instalação
   **continua sozinha** (aceite de novo o pedido de administrador).
2. Instala o `usbipd-win` (leva a placa USB para o Linux).
3. Instala `git` e o Python do Ubuntu.
4. Baixa este projeto para `C:\pokeldn-distrib` (ou atualiza, se já existir).
5. Baixa o pokeldn na versão testada (`89f761e`) e instala as dependências Python.
6. Copia o `prod.keys` que você escolher para o lugar certo (`~/.switch/prod.keys`, permissões
   só para você). **Nunca** fica dentro da pasta do projeto.
7. Baixa o catálogo de eventos (Events Gallery, ~56 MB).
8. Compartilha a placa com o WSL e cria o atalho.
9. Roda a checagem final.

Pode rodar de novo quando quiser: ele pula o que já está pronto. Serve também para **atualizar**
(baixa a versão nova do projeto). Para baixar o catálogo de novo, rode antes, no mesmo
PowerShell: `$env:DISTRIB_ATUALIZAR_CATALOGO = 1`.

O log fica em `C:\ProgramData\pokeldn-distrib\instalar.log`.

## Testar em casa

1. Dois cliques no atalho **Distribuidor de Eventos**.
2. A checagem tem que mostrar tudo com ✓: placa, `prod.keys` e os dois catálogos.
3. Distribua um evento para o seu próprio console (roteiro em `docs/testes-reais.md`).

## No evento

- **Plugue a placa antes de abrir o atalho.**
- Escolha o jogo → digite a busca → **Enter** vai para a lista → escolha o evento → **Enter**.
- **Sword/Shield:** os jogadores vão em Presente Misterioso → Receber presente → Por comunicação
  local. Vários ao mesmo tempo.
- **FireRed/LeafGreen:** um de cada vez, em MYSTERY GIFT → WONDER CARDS → FRIEND. Cada um precisa
  de **um espaço livre na equipe**.

### Problemas comuns

| Mensagem | O que fazer |
|---|---|
| "Placa ESP32 não encontrada" | Use um cabo de dados, troque de porta USB e abra o atalho de novo |
| "A placa ainda não foi compartilhada" | Rode, como administrador, o `usbipd bind --busid …` que a mensagem mostra (ou rode o instalador de novo com a placa plugada) |
| "placa desconectada" na tela No ar | Replugue a placa; a distribuição volta sozinha |
| "PAROU depois de 3 falhas seguidas" | Aperte T, escolha o evento de novo; se repetir, veja o arquivo do dia em `logs\` |
| "equipe cheia" (FRLG) | Peça para o jogador liberar um espaço na equipe e tentar de novo |
| `prod.keys` com ✗ | Rode o instalador de novo e escolha o arquivo na janela |
