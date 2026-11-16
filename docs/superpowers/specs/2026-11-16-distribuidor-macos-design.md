# Distribuidor de Eventos no macOS — design

Data: 2026-11-16. Status: aprovada pelo dono em 2026-11-16.

## Objetivo
Fazer o Distribuidor rodar no macOS como 4ª plataforma oficial (depois de Windows, Linux e Android), com um asset próprio publicado automaticamente pela release `v*`.

## Decisões do dono
- **Somente Apple Silicon (arm64)**, buildado no runner `macos-14`. Intel fica de fora.
- **Sem assinatura nem notarização.** O README ensina a liberar o app na primeira abertura (Ajustes > Privacidade e Segurança > "Abrir mesmo assim", ou `xattr -dr com.apple.quarantine Distribuidor.app`).
- **Teste real feito por um amigo/usuário com Mac.** O dono não tem Mac. Por isso o aceite tem roteiro escrito, e a primeira release do Mac sai marcada como experimental nas notas.

## Base: o upstream já suporta macOS
O pokeldn v0.5.0 (submódulo) publica `pokeldn-macos-arm64.zip` sem assinatura e roda o host via ESP32 com IP em userspace no macOS. Vamos reaproveitar:
- `scripts/pack_flet.py::assemble_macos_view`: o Flet 1.0.2 re-assina o viewer **sem** o entitlement `com.apple.security.files.user-selected.read-write`. Sem ele, o seletor do `prod.keys` falha com `ENTITLEMENT_NOT_FOUND`. Precisamos do mesmo contorno no nosso `build/pack.py` (importar a função do upstream, se ela for importável sem efeitos colaterais; senão, copiar o padrão, já que o distrib é MIT e só importa o AGPL).
- Dados em `~/Library/Application Support/<app>`, como em `pokeldn/app/paths.py`.

## Mudanças no código (pontos levantados pelo grep)
| Onde | Mudança |
|---|---|
| `distrib/platform/__init__.py` | `IS_MACOS = sys.platform == "darwin"` |
| `distrib/config.py` | pasta de dados `~/Library/Application Support/Distribuidor` no macOS |
| `distrib/pokeldn_path.py` | aceitar `darwin` no PKHeX embutido (`pokeldn-pkhex`, `osx-arm64`) |
| `distrib/runner.py` | o ramo POSIX (SIGINT via `pthread_kill`, `POKELDN_L2=userspace`) vale também para o macOS, não só para `linux` |
| `distrib/update.py` | asset `Distribuidor-macos-arm64.zip`; ver "Atualização" |
| `ui/app.py`, `ui/views/ajustes.py`, `ui/views/placa.py` | ícone `icon.png`/`.icns`; "abrir pasta" com `open`; sem dica de dialout/udev no Mac |
| Porta da placa | `list_ports` no macOS lista `/dev/cu.*` e `/dev/tty.*`: preferir `cu.*` e filtrar as portas Bluetooth/debug |
| `build/pack.py` | ramo `darwin`: PKHeX `dotnet publish -r osx-arm64`, `flet pack` gerando `Distribuidor.app` com o contorno de entitlements, e `ditto -c -k --keepParent` → `Distribuidor-macos-arm64.zip` |
| `.github/workflows/release.yml` | job `build-macos` (`macos-14`, `continue-on-error`) que anexa o `.zip` quando existir; uma falha do Mac não trava a release das outras plataformas |
| `README` | seção macOS: requisitos, liberação na 1ª abertura, driver (CH9102/CP2102 são nativos no macOS 11+) |

## Atualização (recomendação)
Na v1 do Mac, o app **avisa da versão nova, baixa o `.zip`, confere o sha256 e mostra o arquivo no Finder** (`open -R`). Quem atualiza é o usuário, arrastando o app. A troca automática do `.app` em execução (script destacado que espera o app fechar, troca o bundle e reabre) fica para depois de o aceite do Mac passar. Assim evitamos depurar um auto-update sem ter Mac.

## Aceite (roteiro para o testador)
1. Baixar o `.zip`, extrair, liberar o app e abrir.
2. Placa no USB: aparece a porta `/dev/cu.*`; "Preparar placa" ok.
3. Selecionar o `prod.keys` (valida o entitlement).
4. "Baixar eventos" ok.
5. SwSh: um Mystery Gift aprovado pelo PKHeX e recebido no console.
6. FRLG: um evento entregue (status 2).
7. Aviso de atualização: com uma versão falsa mais antiga, o app avisa, baixa e mostra o arquivo.
O testador manda o log (pasta de dados) se algo falhar.

## Fora do escopo
Intel/universal2, assinatura e notarização, `.dmg` e auto-update com troca automática do `.app`.

## Riscos
- **Sem Mac próprio:** cada correção depende do testador. Mitigação: os testes unitários rodam no `macos-14` do CI, e um smoke test do `.app` congelado roda no CI (`--module distrib.runners.hello` sem placa, só para checar imports e PKHeX).
- **PKHeX osx-arm64:** o .NET publica para o macOS, mas o binário não é assinado. Pode precisar de `codesign --sign -` (ad hoc) dentro do bundle.
