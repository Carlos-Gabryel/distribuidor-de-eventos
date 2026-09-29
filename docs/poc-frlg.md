# Prova de conceito FRLG: `.pk3` do Events Gallery no FireRed

- **Data:** 2026-09-28, ~21:20
- **Console:** Switch 2 do dono, FireRed (save "Gabry"), MYSTERY GIFT → WONDER CARDS → FRIEND
- **Placa:** Nerdsking ESP32 WROOM-32E (`/dev/ttyACM0`, firmware do pokeldn `idf=v6.1`)
- **Arquivo:** `Released/Gen 3/ENG/10th Anniversary Celebration/Top 10 Distribution/RSEFL - 10ANNIV Lugia (ENG).pk3`
  (LUGIA Nv70, OT 10ANNIV, PID `828027a9`)

## Comando

```bash
wsl.exe -u root -- bash -lc 'cd /mnt/c/Gabry/Projects/pokeldn-distrib && POKELDN_RADIO=esp32:/dev/ttyACM0 \
  /home/gabryel/.venvs/pokeldn/bin/python -u -m distrib.runners.frlg_session \
  --pokeldn /mnt/c/Gabry/Projects/pokeldn --pk3 "<o .pk3 acima>" \
  --keys <prod.keys> --phy auto --idle-timeout 900'
```

## Linhas do log usadas pelo parser (`distrib/games/frlg.py`)

- **(a) no ar:** `[    0.2s] Hosting. Waiting for the console to join (ssid=b19e9397..., channel 1).`
  (o `Advertising ACTIVITY_WONDER_CARD…` sai **antes** de a rede existir, então não serve)
- **(b) console entrou:** `[  870.7s] A console joined the network.`
- **(c) resultado:** `[  890.8s] Mystery Event script status: 2 (success)`, depois
  `Result: Wonder Card sent`, fechamento normal e **código de saída 0**.

Outras linhas úteis: `Console identified itself: 'Gabry' … on FireRed, holding no Wonder Card`,
`Mystery Event script: givepokemon 8; end`.

## Resultado

- Host: **entregue** (status 2, saída 0). Do console entrar até o fim: ~30 s.
- No jogo: **confirmado pelo dono.** O Lugia chegou na equipe do FireRed, nível 70, OT **10ANNIV**.

**Conclusão:** um `.pk3` do Events Gallery chega intacto a um FireRed de verdade pelo `givepokemon`. O catálogo FRLG de `.pk3` fica na v1.
