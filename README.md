# Distribuidor de Eventos (pokeldn-distrib)

Uma interface de terminal para **distribuir Pokémon de evento que não podem mais ser recebidos**
em encontros, a partir de um notebook Windows com uma placa ESP32 no USB. Os consoles recebem
sem nenhuma modificação.

- **Sword/Shield:** os 925 Wonder Cards arquivados pelo Events Gallery. O notebook anuncia o
  cartão e **vários consoles recebem ao mesmo tempo** (Presente Misterioso → Receber presente →
  Por comunicação local).
- **FireRed/LeafGreen:** os Pokémon de evento da Gen 3 (10ANIV, Aura Mew, WISHMKR Jirachi…),
  entregues **byte a byte** (OT, ID e PID originais) direto na equipe, **um console por vez**
  (MYSTERY GIFT → WONDER CARDS → FRIEND), com rodízio de PID entre as entregas. Também traz os
  presentes montados pelo pokeldn (Altering Cave, Battle Count Card…).

Depende do [pokeldn](https://github.com/Decryptu/pokeldn), fixado no commit `89f761e`, que faz
todo o trabalho de rádio e protocolo. Este projeto só o usa, sem modificá-lo.

## Instalar

Veja [docs/instalacao.md](docs/instalacao.md): WSL, `prod.keys` e o `windows\instalar.ps1`.

## Usar

1. Plugue a placa e abra o atalho **Distribuidor de Eventos** (ou `Iniciar Distribuicao.bat`).
2. A checagem mostra placa, `prod.keys` e catálogos. `Enter` continua, `R` checa de novo.
3. Escolha o jogo, digite a busca e aperte `Enter` para ir à lista (`Tab` alterna entre busca e
   lista). Escolha o evento e aperte `Enter`.
4. Na tela **No ar**: `T` troca de evento (o atual continua no ar até você escolher outro),
   `P` pausa/retoma, `Q` sai.

No catálogo: `F` marca/desmarca o evento na **vitrine do dia** (aparece no topo), `I` mostra
também itens, roupas e BP (Sword/Shield), `Esc` volta.

## Linha de comando

```bash
python -m distrib                       # a interface
python -m distrib checar                # placa, prod.keys e catálogos
python -m distrib atualizar-catalogo    # baixa o Events Gallery de novo (swsh, frlg ou ambos)
```

Os logs de cada dia ficam em `logs/AAAA-MM-DD.log`; a vitrine e o rodízio de PID em `state/`.

## Desenvolvimento

Os testes rodam no WSL, com o venv do pokeldn:

```bash
~/.venvs/pokeldn/bin/python -m pytest
```

O design está em `docs/superpowers/specs/` e o plano em `docs/superpowers/plans/`.

## Créditos

- [pokeldn](https://github.com/Decryptu/pokeldn), de Decryptu (AGPLv3): LDN, Pia e os protocolos
  dos jogos.
- [Events Gallery](https://github.com/projectpokemon/EventsGallery), do Project Pokémon: o
  arquivo das distribuições oficiais.
- [kinnay/LDN](https://github.com/kinnay/LDN): a biblioteca LDN que o pokeldn usa.
