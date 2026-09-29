# Instalação no notebook

Passo a passo para deixar um notebook Windows pronto para distribuir eventos. Faça tudo **em casa,
com internet**. No evento, a internet não é necessária.

## 1. O que você precisa

- Notebook com Windows 10 ou 11.
- A placa ESP32 **já gravada** com o firmware do pokeldn. A gravação é feita uma vez no PC de casa:
  no WSL, `cd pokeldn/firmware/esp32 && idf.py -p /dev/ttyACM0 flash`. O notebook não precisa
  do ESP-IDF.
- Um **cabo USB de dados** (cabos só de carga não funcionam).
- O `prod.keys` do seu próprio console.
- Esta pasta (`pokeldn-distrib`), copiada para o notebook, por exemplo em `C:\pokeldn-distrib`
  (via `git clone` ou pendrive).

## 2. WSL (Linux dentro do Windows)

1. Abra o **PowerShell como administrador** (clique direito no menu Iniciar → "Terminal (Admin)").
2. Rode `wsl --install -d Ubuntu-24.04`.
3. Reinicie o notebook, se ele pedir.
4. Abra o app **Ubuntu** no menu Iniciar e crie um usuário e uma senha (anote a senha).

## 3. O `prod.keys`

No terminal do Ubuntu:

```bash
mkdir -p ~/.switch && chmod 700 ~/.switch
cp /mnt/d/prod.keys ~/.switch/prod.keys     # troque /mnt/d/ pelo lugar onde o arquivo está
chmod 600 ~/.switch/prod.keys
```

`C:\` aparece como `/mnt/c/`, um pendrive em `D:\` como `/mnt/d/`. **Nunca** coloque o
`prod.keys` dentro da pasta do projeto.

## 4. Instalação automática

1. **Plugue a placa** no notebook.
2. No PowerShell como administrador:

   ```powershell
   powershell -ExecutionPolicy Bypass -File C:\pokeldn-distrib\windows\instalar.ps1
   ```

   Ele instala o `usbipd-win`, baixa o pokeldn (versão testada, `89f761e`), cria o ambiente
   Python, baixa o catálogo de eventos (~56 MB), compartilha a placa com o WSL e cria o atalho
   **"Distribuidor de Eventos"** na área de trabalho. Leva alguns minutos.

## 5. Teste em casa

1. Dois cliques no atalho **Distribuidor de Eventos**.
2. A tela de checagem tem que mostrar tudo com ✓: placa, `prod.keys` e os dois catálogos.
3. Distribua um evento para o seu próprio console (roteiro em `docs/testes-reais.md`).

## 6. No evento

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
| "A placa ainda não foi compartilhada" | Rode, como administrador, o `usbipd bind --busid …` que a mensagem mostra (só na primeira vez em cada porta/placa) |
| "placa desconectada" na tela No ar | Replugue a placa; a distribuição volta sozinha |
| "PAROU depois de 3 falhas seguidas" | Aperte T, escolha o evento de novo; se repetir, veja o arquivo do dia em `logs\` |
| "equipe cheia" (FRLG) | Peça para o jogador liberar um espaço na equipe e tentar de novo |
