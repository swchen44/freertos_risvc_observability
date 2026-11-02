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
Task 3: complete (commits fe41cbf..8776695, tests: env PYTHONPATH=src .venv/bin/python -m unittest tests.unit.test_clock_anchor_native -v → OK)

Task 3: 6 native tests including 27 negative/guard scenarios; clean-tree full suite 348/348; new Python format and Ruff passed.
Ruling: add an unmodified pinned upstream QEMU symbol-generator fixture with license/provenance in references/qemu-clock-anchor — export tests must execute the real generator without a new network dependency — cost if wrong: fixture must be refreshed when the pinned QEMU version changes.
Ruling: patch generator accepts sparse edited trees and only nine named paths; omitted paths are unchanged, deletion unsupported — avoid another 817MiB source copy on a disk with 5.3GiB free — cost if wrong: future deletions require a new explicit interface.
Global format: 10 baseline files fail the same formatter at 9c3c9aef; full Ruff check and all new-file format checks pass. This remains an open global check, not suppressed or counted as passed.

Task 4: first build failed at target/riscv/cpu.c:2822 (implicit tolower declaration). Root cause: my global -Iinclude/qemu made QEMU ctype.h shadow system <ctype.h>.
Ruling: private core header selects qemu/poc-clock-anchor-api.h only under POC_CLOCK_IN_QEMU; Meson defines that flag without adding include/qemu globally — fixes header shadowing while keeping one byte-identical canonical core — cost if wrong: rebuild and native dual-include test fail; first build retained.

Task 4: retry2 compiled/linked. First manifest step failed because ninja CLI reports 1.13.2.git.kitware.jobserver-pipe-1 while installed distribution is pinned 1.13.2; added RED/GREEN package-versus-executable validation, no binary recompile for metadata recovery.
Task 4: ABI first positive run exposed native-io-pending (ABI probe lacked MMIO success callbacks) and hung. macOS sample of the owned QEMU confirms exit -> qemu_plugin_atexit_cb -> poc_clock_finish -> mutex wait while fatal path holds clock_lock. Fix releases the lock before fatal exit, as plan requires; new explicit missing-MMIO runtime rejection must finish without timeout. Original run/sample retained.

Task 4 checkpoint 2026-11-03: retry3 build complete; manifest .tools/c2b-clock-20261102-r3/build-manifest.json; binary SHA eab95b72dabe404d652bba976d821892b276b0c06be1f92fd305c7bdb30f42e6. ABI CLI tests/integration/clock_anchor_abi.py passed all 10 subcases in runs/local/c2b-abi-20261103, no timeout/skip. Prior runs/local/c2b-abi-20261102-r1 failed normal with 120s timeout; macOS sample confirms held-lock cleanup deadlock, fixed by 797d8c7c. Six old/new nano,b burst,edges driver runs are in runs/local/c2b-clock-regressions-20261103, commands/results after each. Task4 not complete until six drivers and full suite/receipts verified.
Task 4: complete (commits 8776695..797d8c7, tests: env PYTHONPATH=src .venv/bin/python -m unittest tests.unit.test_clock_anchor_build tests.unit.test_clock_anchor_native -v → OK)

2026-11-03 user steering: audit disk space in artifacts/runs. Scope question pending; no files removed. Exact archived-copy checks and clone/cache inventory saved at artifacts/verification/storage/20261103/audit.json. Tasks1–4 were pushed: POC be50f8b9700fedcec29efb6b791811a7979535c4 and root 8fb56f808ab5b47087299ef0fbe13f8167b2332f; remote SHAs matched and both were clean. Task5 brief taken, BASE be50f8b9; no Task5 product/test code yet.

2026-11-03 user OK, contine jobs: conservative cleanup authorized and completed. Receipt artifacts/verification/storage/cleanup-20261103-r2. Four archived copies reverified (946 files), disposable clean clone and 3305 generated objects removed. No tracked/unique trace files removed; relative/new QEMU and active probe ELF hashes preserved. Observed free delta 590680064 bytes. First preflight stopped before deletion on legacy Ninja path mismatch, retained separately. Resume Task5, no Task5 product/test code yet.

Task 5: Python and plugin native tests written and watched RED (missing modules/header).
Task 5: Ruling: clock_anchor_init accepts (config_path, handle, begin_pc, end_pc) — existing collector already owns the unique time-control handle and capture boundary PCs, absent from the proposed clock config; pass them explicitly instead of a second ownership request or extra mutable setters — cost if wrong: coordinated internal signature update; public QEMU ABI unchanged.
Task 5: 12 targeted tests GREEN (capture 6, boundaries 2, native helper 4); canonical QEMU source and smoke artifact guards watched RED/GREEN. macOS /var versus /private/var output test now checks samefile; production canonicalization unchanged. CLI --help and changed Python format/Ruff pass. Formal run_pilot deliberately depends on independent Tasks6/7 validator/comparator and is not yet executed.
Ruling: lossless gzip after each capture, verify decompressed SHA before deleting only its uncompressed duplicate — preserve every raw/context/clock record within disk budget after user-approved cleanup — cost if wrong: explicit gzip read support required in validator/restore; compressed and content SHA both recorded.
Task 5: complete (commits be50f8b..1bba920, tests: env PYTHONPATH=src .venv/bin/python -m unittest tests.unit.test_clock_anchor_capture tests.unit.test_clock_anchor_boundaries tests.unit.test_clock_anchor_plugin -v → OK)
