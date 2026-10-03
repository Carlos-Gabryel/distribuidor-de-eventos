# Testes reais (placa + consoles)

Roteiro da spec, seção 9.2. Preencha a data e o resultado de cada item. Um item que falhar vira
bug em `Known Bugs/pokeldn - bugs.md` no vault, com o trecho do log de `logs/`.

| # | Teste | Como | Data | Resultado |
|--:|---|---|---|---|
| 1 | Prova de conceito FRLG | `.pk3` 10ANIV Lugia pelo runner (plano, Task 2); resultado em `docs/poc-frlg.md` | 2026-09-28 | **ok**: Lugia 10ANIV na equipe do FireRed, Nv70, OT 10ANNIV (status 2, saída 0); detalhes em `docs/poc-frlg.md` |
| 2 | SwSh com cartão do Events Gallery | abrir o `Distribuidor.exe` → Distribuir → Sword/Shield → "Jungle Zarude (Western Release)" → o Sword recebe o Zarude Nv60 com OT do evento | 2026-09-28 | **ok**: pelo atalho (checagem ✓ → Sword/Shield → busca "zarude" → No ar); o Zarude chegou no Sword do dono (Switch 2) |
| 3 | Regiões SwSh | Um cartão "(Japanese Release)" e um "(Western Release)" no mesmo Sword | 2026-09-28 | **ok, com observação**: o cartão "(Japanese Release)" chegou, mas o Pokémon veio **em inglês**. Os três arquivos regionais do Zarude trazem OT nos 9 idiomas (オコヤのもり, Jungle, Giungla, …): o cartão é multilíngue e o jogo usa o bloco do idioma do save. Comportamento do jogo, não da ferramenta |
| 4 | FRLG equipe cheia | Equipe com 6 → a tela mostra "equipe cheia"; liberar um espaço → entrega na sessão seguinte | 2026-09-28 | **ok**: "equipe cheia" apareceu com a equipe completa; com um espaço livre, entregou na sessão seguinte |
| 5 | FRLG rodízio de PID | Duas entregas seguidas de um evento com várias variantes → PIDs diferentes (linha "Última" da tela) | 2026-09-28 | **ok**: entregas seguidas do JIRACHI (WISHMKR, ENG) com PIDs diferentes |
| 6 | Trocar de evento | SwSh no ar → escolher outro evento; no FRLG, trocar entre dois consoles | 2026-09-28 | **ok**: T → outro evento → Enter; voltou a "NO AR" com o evento novo |
| 7 | Placa desplugada | Com o SwSh no ar, desplugar e replugar a placa (a porta `COMx` pode mudar) → "placa desconectada" → volta sozinho | 2026-09-28 | **ok**: desplugada → "placa desconectada"; replugada → voltou a distribuir sozinha após alguns segundos |
| 8 | Ensaio geral no notebook | Sem internet, a partir do `Distribuidor.exe`, repetindo os itens 2 e 4 | 2026-09-29 | **ok**: instalação do zero no notebook pela linha `irm …/instalar.ps1 | iex` (depois da correção do WSL ausente, commit `ec632f7`); o dono testou a distribuição e tudo funcionou |
| 9 | Preparar placa | Apague a placa (`esptool --port COMx erase-flash`), abra o app, aba Placa → Preparar placa → Gravar | | Esperado: barra até 100%, "Placa preparada.", cartão lateral verde |
| 10 | Atualização | Com a v2.0.0 aberta e um Release v2.0.1 publicado | | Esperado: "Atualização v2.0.1 pronta"; "Reiniciar" abre a v2.0.1 e o `Distribuidor.exe.old` some na abertura seguinte |

Os itens 1 a 8 foram feitos na versão antiga (WSL + TUI); o resultado vale como histórico e
será repetido com o `.exe` na Task 18.

## Observação sobre idiomas (Sword/Shield)

Os cartões de Gen 8 que trazem textos nos 9 idiomas entregam o Pokémon **no idioma do jogo
que recebe**, qualquer que seja a "Release" escolhida. Para um jogador receber um Pokémon
"japonês", seria preciso um cartão com um único idioma (poucos eventos são assim).
