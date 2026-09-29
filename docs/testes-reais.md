# Testes reais (placa + consoles)

Roteiro da spec, seção 9.2. Preencha a data e o resultado de cada item. Um item que falhar vira
bug em `Known Bugs/pokeldn - bugs.md` no vault, com o trecho do log de `logs/`.

| # | Teste | Como | Data | Resultado |
|--:|---|---|---|---|
| 1 | Prova de conceito FRLG | `.pk3` 10ANIV Lugia pelo runner (plano, Task 2); resultado em `docs/poc-frlg.md` | 2026-09-28 | **ok**: Lugia 10ANIV na equipe do FireRed, Nv70, OT 10ANNIV (status 2, saída 0); detalhes em `docs/poc-frlg.md` |
| 2 | SwSh com cartão do Events Gallery | TUI → Sword/Shield → "Jungle Zarude (Western Release)" → o Sword recebe o Zarude Nv60 com OT do evento | 2026-09-28 | **ok**: pelo atalho (checagem ✓ → Sword/Shield → busca "zarude" → No ar); o Zarude chegou no Sword do dono (Switch 2) |
| 3 | Regiões SwSh | Um cartão "(Japanese Release)" e um "(Western Release)" no mesmo Sword | 2026-09-28 | **ok, com observação**: o cartão "(Japanese Release)" chegou, mas o Pokémon veio **em inglês**. Os três arquivos regionais do Zarude trazem OT nos 9 idiomas (オコヤのもり, Jungle, Giungla, …): o cartão é multilíngue e o jogo usa o bloco do idioma do save. Comportamento do jogo, não da ferramenta |
| 4 | FRLG equipe cheia | Equipe com 6 → a tela mostra "equipe cheia"; liberar um espaço → entrega na sessão seguinte | 2026-09-28 | **ok**: "equipe cheia" apareceu com a equipe completa; com um espaço livre, entregou na sessão seguinte |
| 5 | FRLG rodízio de PID | Duas entregas seguidas de um evento com várias variantes → PIDs diferentes (linha "Última" da tela) | 2026-09-28 | **ok**: entregas seguidas do JIRACHI (WISHMKR, ENG) com PIDs diferentes |
| 6 | Trocar de evento | SwSh no ar → `T` → outro → `Enter`; no FRLG, trocar entre dois consoles | 2026-09-28 | **ok**: T → outro evento → Enter; voltou a "NO AR" com o evento novo |
| 7 | Placa desplugada | Com o SwSh no ar, desplugar e replugar → "placa desconectada" → volta sozinho | 2026-09-28 | **ok**: desplugada → "placa desconectada"; replugada → voltou a distribuir sozinha após alguns segundos |
| 8 | Ensaio geral no notebook | Sem internet, a partir do atalho, repetindo os itens 2 e 4 | 2026-09-29 | **ok**: instalação do zero no notebook pela linha `irm …/instalar.ps1 | iex` (depois da correção do WSL ausente, commit `ec632f7`); o dono testou a distribuição e tudo funcionou |

## Observação sobre idiomas (Sword/Shield)

Os cartões de Gen 8 que trazem textos nos 9 idiomas entregam o Pokémon **no idioma do jogo
que recebe**, qualquer que seja a "Release" escolhida. Para um jogador receber um Pokémon
"japonês", seria preciso um cartão com um único idioma (poucos eventos são assim).
