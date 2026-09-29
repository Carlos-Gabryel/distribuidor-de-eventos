# SDD ledger — plan: docs/superpowers/plans/2026-09-28-distribuidor-eventos.md
Spec: docs/superpowers/specs/2026-09-28-distribuidor-eventos-design.md
Setup: Ruling: feature branch feat/distribuidor instead of a worktree — new single-owner repo, isolation by branch is enough — cost if wrong: none (merge later).
Pre-flight:
- T1→T2: ensure_importable(Path) produced/consumed — ok
- T3→T4/T5: Event/Catalog/save_index fields match adapters' use — ok
- T2→T5: frlg_gift.load_mon/GiftError — ok
- T4/T5→T6: build_catalog(raw_dir, cfg); RAW_PREFIX strings equal SWSH_RAW/FRLG_RAW — ok
- T3/T7: run_checks(cfg, catalogs) uses Catalog.events — ok
- T4→T8: Update fields/Adapter.mode — ok
- T8→T9: Distributor(mode, parse_line, job_factory, log_path, find_port, max_failures=) matches default_services — ok
- T9→T10: services() test helper returns None distributor in T9; T10 step changes it to FakeDistributor — ok (planned)
- T7/T9→T11: default_services, radio.run_checks — ok
Task 1: complete (commits efaa763..4bece0c, tests: wsl.exe -- bash <pytest no WSL> tests/test_config.py -q → 3 passed in 0.09s)
Task 2: code committed a74d273 (6/6); PoC host running, waiting for owner's FireRed
Task 3: complete (commits a74d273..c2f99b3, tests: wsl.exe -- bash <pytest no WSL> tests/test_catalog.py -q → 7 passed in 0.10s)
Task 4: complete (commits c2f99b3..59f2170, tests: wsl.exe -- bash <pytest no WSL> tests/test_swsh.py -q → 6 passed in 0.30s)
Task 5: Ruling: FRLG on_air = line "Hosting. Waiting for the console to join (…, channel N)" (also gives channel), not "Advertising ACTIVITY_WONDER_CARD" — real PoC log shows Advertising printed before the network is up — cost if wrong: on_air shown ~0.2 s late
Task 5: added test_extras_exist_in_the_pokeldn_registry (guards EXTRAS slugs); _CONSOLE ("joined") still pending PoC confirmation
Task 5: complete (commits 59f2170..02fca35, tests: wsl.exe -- bash <pytest no WSL> tests/test_frlg.py tests/test_swsh.py -q → 14 passed in 1.41s)
Task 6: Ruling: plan Step 5 one-liner lacked ensure_importable(cfg.pokeldn_dir) — added it (update_catalogs imports pokeldn via adapters) — cost if wrong: none. Dropped unused SUFFIX dict from plan code.
Task 7: real HELLO check (Step 5) deferred until the PoC host frees the board
Task 8: Ruling: session fake-host scripts use the "Hosting. Waiting…" line (Task 5 ruling) instead of "Advertising ACTIVITY_WONDER_CARD." — keeps tests consistent with the parser — cost if wrong: none
Task 8: complete (commits f5e990f..c16dc14, tests: wsl.exe -- bash <pytest no WSL> tests/test_distributor.py -q → 9 passed in 2.68s)
Task 9: complete (commits c16dc14..12ec12c, tests: wsl.exe -- bash <pytest no WSL> tests/test_app.py -q → 4 passed in 2.80s)
Task 6/5: Ruling: FRLG events grouped by data (folder + species + OT + TID + language), named "<SPECIES> (<OT>, <LANG>)", instead of by filename minus PID tag — real Gallery numbers variants with serials ("MYSTRY (001 of 430) Mew", "PCNYc 00001 Gloom"), so the filename rule made 426 Mew "events" — cost if wrong: two genuinely different distributions with same species/OT/TID/lang in one folder merge into one event (acceptable: rotation still serves each file)
Task 10: complete (commits ed07ebe..e6d9eed, tests: wsl.exe -- bash <pytest no WSL> tests/test_app.py -q → 7 passed in 4.11s)
Task 11: real "checar" with the board (Step 5) deferred with Task 7 Step 5 until the PoC frees the board
Task 6/5: Ruling (revised): grouping key drops TID → folder + species + OT + language; details show "TID: vários" when variants differ — PCNY redemptions each carry a unique TID, so TID split one event into ~70 — cost if wrong: two different-TID distributions of same species/OT/lang in one folder merge (rotation still serves every file)
Task 12: Ruling: launcher reads the configured python path via windows/caminho_python.py (system python3 + tomllib) instead of the inline one-liner — the nested PowerShell→bash→python quoting was fragile — cost if wrong: none. .ps1 with accents saved UTF-8 with BOM (PowerShell 5.1 reads BOM-less files as ANSI).
Task 12: manual double-click test (Step 6) deferred until the board is free
Task 13: Ruling: dialout group added via "wsl -u root -- usermod -aG dialout <user>" instead of "sudo usermod … $USER" — avoids an interactive sudo password prompt in the installer — cost if wrong: none
Task 13: complete (commits 426d571..3ea5585, tests: powershell.exe -NoProfile -Command '$null = [scriptblock]::Create((Get-Content -Raw -Encoding UTF8 windows\instalar.ps1)); 'sintaxe ok'' → sintaxe ok)
Task 6: real catalogs: SwSh 925 events/0 invalid; FRLG 258 events (248 + 10 extras) from 2588 valid .pk3; all 589 invalid are eggs (excluded by design, v1)
Real check 2026-09-28 21:2x: "python -m distrib checar" as root → Placa ✓ (/dev/ttyACM0, idf=v6.1), prod.keys ✓, SwSh 925 ✓, FRLG 258 ✓, EXIT=0 (covers Task 7 Step 5 and Task 11 Step 5)
Task 6: complete (commits efaa763..a45e97b, tests: wsl.exe -- bash <pytest no WSL> tests/ -q → 57 passed in 9.46s)
Task 7: complete (commits efaa763..a45e97b, tests: wsl.exe -- bash <pytest no WSL> tests/ -q → 57 passed in 9.45s)
Task 11: complete (commits efaa763..a45e97b, tests: wsl.exe -- bash <pytest no WSL> tests/ -q → 57 passed in 9.38s)
Final review: fresh reviewer (opus). Verdict: with fixes. Fix pass: C1, C2, I1, I2, I3.
Final: minor (deferred): M1 FRLG "Última" shows the next session's PID right after a delivery (spec wants the delivered PID)
Final: minor (deferred): M2 R on the check screen runs HELLO while a distribution holds the port (Esc Esc R route)
Final: minor (deferred): M3 log opened per line on drvfs; no size cap on the daily log
Final: minor (deferred): M4 "Último erro" can show "Traceback (most recent call last):" instead of the real error line
Final: minor (deferred): M5 two serial ports → "Plugue a placa" instead of "mais de uma porta serial"
Final: minor (deferred): M6 SwSh keys positional (0003.wc8): favorites may point to other cards after atualizar-catalogo adds one
Final: minor (deferred): M7 atualizar-catalogo deletes the catalog before rebuilding (no temp+swap)
Final: minor (deferred): M8 iniciar.ps1: Fail paths leave the hidden wsl sleep; $userHome fragile; "Shared (forced)" not matched
Final: minor (deferred): M9 instalar.ps1 never checks $LASTEXITCODE (prints "Pronto" after a failed step)
Final: minor (deferred): M10 stop() blocks the Textual loop up to ~25 s during a switch
Final: fixed C1 board lost mid-run — test_board_lost_mid_run_goes_no_board_then_recovers RED→GREEN, suite 63/63 (729123d)
Final: fixed C2 stop/pause spawn race — test_stop_during_slow_job_factory_leaves_no_process + test_pause_right_before_spawn_does_not_start_a_host RED→GREEN, suite 63/63
Final: fixed I1 FRLG crash loop — test_session_crash_before_air_counts_failure RED→GREEN, suite 63/63
Final: fixed I2 SIGTERM skips pokeldn cleanup — test_stop_interrupts_the_host_with_sigint RED→GREEN, suite 63/63
Final: fixed I3 rotation per session not per delivery — test_rotation_advances_only_on_delivery + test_on_delivered_runs_once_per_delivery RED→GREEN, suite 63/63
Final: Ruling: reviewer "Declined to judge" lines (ESP32 state after host death without STOP; baud reset between runs; SIGHUP on window close; --no-validate; Gallery provenance) — covered by I2 (SIGINT) and by the real runs that worked; the rest are spec choices — cost if wrong: a stuck board needs a replug
Task 2: complete (commits 4bece0c..f3b5a35, tests: wsl.exe -- bash <pytest no WSL> tests/test_frlg_gift.py -q → 6 passed in 1.42s)
Task 12: manual test found bug: wsl.exe strips backslashes in wslpath arg → ConvertTo-WslArg (test RED→GREEN, 6/6); launcher now traps errors and .bat pauses on failure (b164c91)
Task 12: complete (commits 4851315..e556795, tests: powershell.exe -NoProfile -ExecutionPolicy Bypass -File windows\tests\usb.Tests.ps1 → 6 ok, 0 falhas)
Task 14: real tests 1–7 ok (2026-09-28); test 8 (notebook rehearsal, offline) pending the owner's laptop
Task 14: complete (commits 215bbfb..7208a76, tests: wsl.exe -- bash <pytest no WSL> tests/ -q → 63 passed in 14.45s)
