# SDD ledger — plan: docs/plans/20-c2b-clock-anchor-implementation.md

2026-11-02 使用者 continue 確認實作計畫；Native 執行。Baseline POC 9c3c9aef，root c7310be。
Ruling: 使用既有 ~/git/percepio/poc 與 feat/psf-lab 分支，工作不移出使用者指定位置；不新增 worktree — 使用者指定 POC 為所有實驗與文件位置且目前乾淨 — 若有同時寫入需停止排查，不能覆蓋他人工作。

## Pre-flight interfaces
| Producers → consumers | Contract check |
|---|---|
| 1 → 3,6 | strict wire schema/canonical decimal/clock quantum；C writer output must pass Python reader |
| 2 → 5,6 | same ELF mode/count oracle, three symbols, five phases; injection remains independent |
| 3 → 4 | standard-only public ABI and private state/sink; generated patch copies verified bytes |
| 4 → 5 | actual new binary/header exports/manifest, preserve old binary |
| 5 → 6,8 | external expected identity and locked small profile; raw_rows from independent replay |
| 6 → 7 | verified bounds with unknown and independent status axes; no inferred timestamps |
| 7 → 8 | exact L/C/C/O checks, O/M differences denominator M, complete/partial reports |
| 8 → future UI | pilot only; no UI acceptance or target PMU/SDK/UART claims |
No interface conflicts found beyond explicitly resolved marker-mode versus injection distinction.

## Tasks
- [ ] 1 Wire reader/math/fixtures (in progress)
- [ ] 2 Guest markers/mode/probe
- [ ] 3 Native observer core
- [ ] 4 QEMU adapter/build/regressions
- [ ] 5 Boundaries/plugin/capture
- [ ] 6 Streaming validation/join
- [ ] 7 Comparisons/report
- [ ] 8 Formal pilot/restore/review/publication

Task 1: baseline 328/328 green; new wire tests 11/11 green; Ruff check/format passed.
Ruling: wire fixes exact clock_domains names, phase values and epoch old_value/new_value; request/marker/MMIO records include pc — spec requires preserving observed PC and strict per-kind schema, plan left key spellings open — cost if wrong: coordinated producer/consumer schema change before captures.
Task 1: full suite while uncommitted rejected priority/logger/queue formal runs (3 errors, dirty-source policy). No guard was bypassed; commit source then rerun clean.
Task 1: complete (commits 9c3c9ae..1b7c0eb, tests: env PYTHONPATH=src .venv/bin/python -m unittest tests.unit.test_clock_anchor_wire -v → OK)
Task 2: complete (commits 1b7c0eb..af002ed, tests: env C2B_REQUIRE_QEMU=1 C2B_RUNTIME_CONFIG=runs/local/c2b-guest-probe-20261102/runtime-tests.json PYTHONPATH=src .venv/bin/python -m unittest tests.unit.test_clock_anchor_guest tests.integration.test_clock_anchor_guest -v → OK)
