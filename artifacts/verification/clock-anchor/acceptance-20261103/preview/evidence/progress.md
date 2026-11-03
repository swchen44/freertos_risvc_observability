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
- [x] 1 Wire reader/math/fixtures
- [x] 2 Guest markers/mode/probe
- [x] 3 Native observer core
- [x] 4 QEMU adapter/build/regressions
- [x] 5 Boundaries/plugin/capture
- [x] 6 Streaming validation/join
- [x] 7 Comparisons/report
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

Task 5: source 1bba920c builds both collectors and candidate ELFs. Development O exits0: 431823 raw rows, 1109492 model cycles, 431823 requests/applied, 5 markers, 78 device/plugin pairs, pending0. Captured-unvalidated only. Full suite 364 executed, 362 passed/2 opt-in skipped; explicit guest runtime 2/2 passed with no skip. Formal pilot remains0.
Task 6: first runtime test setup accidentally shadowed unittest.TestCase.run with a Path; renamed captured_run, preserving original failed log. Standalone wrapper RED then exposed duplicate raw_rows keyword; fixed by replacing the externally null value only with audited row count.
Task 6: development capture independent replay/scan/join produced five verified-bounds, 431512 covered rows and 311 unknown; not yet formal/runtime-suite acceptance.
Ruling: iter_clock_records adds optional content_hasher to hash bytes actually consumed in each scan — pre/post whole-file checks alone cannot detect a temporary swap during parsing — cost if wrong: additive reader argument must remain backward compatible; plain/gzip test compares exact uncompressed SHA. Mode0 consumes pass2 even without anchors.
Task 6: added explicit external mode/tool/whole-command contract, embedded-boundaries/file-hash equality, marker PC versus pinned hook and actual next I-row checks; both command and marker-PC guards watched RED/GREEN.
Task 6: explicit runtime retry2 passed 3/3 in122.126s, no skip: true O capture/bounds, ABI/SMP/bad-cmdline refusals, retained missing-footer/duplicate-request/hash-mismatch copies. Tested commit574a897e; later join refinements require targeted revalidation.
Task 6: full64-wrap RED proved unsigned sdk>=app is wrong across wrap. Fixed order via native quantum and modular counter differences; within-anchor MAX->0 and between-anchor wrap test GREEN.
Ruling: valid native evidence with missing/nonunique SDK candidate returns alignment unavailable and all rows unknown, rather than evidence invalid — matches spec6's distinct evidence/alignment axes — cost if wrong: smoke still must reject absent verified-bounds, so this cannot silently pass pilot.
Task 6: separate enter->sampled and sampled->leave context labels preserve IRQ preemption, with exclusive_cpu_status unavailable; no hook callback is described as retirement. Plain/gzip causal summaries agree; trace16MiB/context65536 row limits and actual validator commit/clean state are recorded.
Task 6: complete (commits 984b78e..5ed35ac, tests: env PYTHONPATH=src .venv/bin/python -m unittest tests.unit.test_clock_anchor_wire tests.unit.test_clock_anchor_evidence tests.unit.test_clock_anchor_join tests.unit.test_clock_anchor_capture -v → OK)

Task 6 final: source5ed35acb full suite385 executed380 passed5 opt-in skips; targeted35/35; final positive O plus guest tests3/3 no skip48.424s. All runtime failed attempts preserved. Formal16 remains0.
2026-11-03 user explicitly paused development and requested disk cleanup before resuming. Task7 stopped after RED tests only; no analysis implementation exists. Draft test moved intact to paused-task7/test_clock_anchor_analysis.py so an unfinished import does not break the paused repository. Task7 BASE11885222. Tasks1–6 already pushed: POC11885222, root57aafb33, both remote verified. Only cleanup/checkpoint/documentation actions until user resumes.
2026-11-03 user continue: resume Task7 from approved brief and original BASE11885222. Restored byte-identical RED test draft; Tasks1–6 not repeated. Pending cleanup publication retried with fixed source commit e0679501 and1800s transport timeout, so later commits cannot change the pushed snapshot. Progress/docs still show historical pause until current acceptance is recorded.
Task7: restored RED -> analysis/report implementation. Additional REDs proved: full stage revalidated smoke only after twelve new captures, smoke omitted O/M application gate, and marker effect ignored differing application outcome. Fixed before any formal capture. Verified-bounds now requires five anchors, not a status flag alone.
Ruling: full stage independently revalidates the four smoke captures before expansion, then keeps fresh validation results in memory for final comparisons instead of replaying all new runs twice — enforces the approved causal gate and avoids redundant scans — cost if wrong: final source/tools and frozen-smoke file checks remain mandatory; independent report generation revalidates every run again.
Task7: CSV preserves signed generated numerics, guards formula labels, UTF8/QUOTE_ALL/CRLF; exact Decimal percentages use M denominator and null on zero. Report fixture tests cover exact16 identities/20 anchor rows; fixtures are formatting/control-flow evidence, not runtime. Real code-size metadata saved at artifacts/local/c2b-code-size-20261103: baseline andpbuf .text39782 versus fixed historical39014, whole-build delta768 bytes; not isolated SDK size. Bounds min/median/max use exact Decimal and remain unrated.
Task 7: complete (commits 1188522..aba298d, tests: env PYTHONPATH=src .venv/bin/python -m unittest tests.unit.test_clock_anchor_analysis tests.unit.test_clock_anchor_pilot_flow tests.unit.test_clock_anchor_capture -v → OK)

Task7 fullsuite396 executed391 passed5 opt-in skips; targeted18/18. Cleanup publication retry e0679501 verified remote, fixed snapshot unaffected by Task7 source changes. No formal captures yet.
Task8: package tests watched RED then5/5 GREEN; per-file gzip parts <=64MiB, self-contained binary/mode restore, partial failed run, wrong/missing part, symlink/traversal/unsupported tar/zip codec and declared-size checks.
Ruling: nested source snapshots are opaque regular tar.gz bytes inside per-file gzip package; their upstream symlink metadata is preserved but never extracted by outer restore — satisfies complete-source retention while outer members reject symlinks/traversal — cost if wrong: source extraction needs a separate inventory-checked step, not an implicit build-ready claim.
Ruling: restore spools one verified concatenated gzip to a temporary file, then streams decompression in64KiB chunks — simple bounded memory and explicit per-part/full-content checks — cost if wrong: restore disk headroom includes largest gzip entry in addition to all original bytes.
Ruling: host GCC distribution, GLib/system libraries and complete offline wheels are not bundled; manifest records locks and offline_rebuild unavailable — approved plan explicitly allows missing offline dependencies and no cross-host target exists — cost if wrong: intranet build requires separately provisioning these pinned host dependencies; data/source restoration remains testable.
Ruling: global format gate retains10 unchanged baseline failures, verified byte-identical to9c3c9aef; full Ruff check and changed-file format must pass — preserve historical source/provenance and spec requires Ruff rather than rewriting old model files — cost if wrong: global formatting debt remains explicit, never reported passed.
Task8 before formal: 401 suite executed396 passed5 skips; explicit runtime5/5 passed122.144s on951a36a7. Subsequent source audit found real collector bug: QEMU plugins/core.c do_plugin_register_cb replaces ctx->callbacks[event] function; live_cache.c registered context_vcpu_init then clock_anchor_vcpu_init. Active O sidecar has trap causes0 and no context_capabilities log. Prior bounds remain timing evidence, but context quality is unknown_cause; NOT accepted formal or exact IRQ attribution. New positive runtime assertions for capability log/mcause/quality must fail before dispatch fix. No formal captures have started.
Task8 dispatch RED: actual fresh O capture test failed12.465s, missing context_capabilities; three trap causes0 confirmed in preserved sidecar. Fixed new opt-in collector to register one dispatcher invoking context_vcpu_init then clock_anchor_vcpu_init. Legacy/frozen source remains unchanged. Runtime test additionally requires mcause_matches1 and context quality exact.
Ruling: rebuild accepted tools into new initfix directory after collector dependency change, with one final ELF per candidate reused by all sixteen captures — old tools hash must fail after C changes and old evidence stays preserved — cost if wrong: new build/ELF identities must be recorded; earlier development bounds are not exact IRQ attribution or formal acceptance.
Task8 formal: four smoke passed then same-source full appended12;16/16 valid, four groups passed on3cdb7794. No smoke overwrite. Independent fresh Astra/high review of9c3..3cdb found2 Important, noCritical/Minor; both findings accepted and reproduced RED. Fix pass adds hook cursor<rows/empty pending markers and bounded immutable manifest snapshot+end identity check. Guest producer/ELF/profile unchanged; final analysis will revalidate existing16 with hardened consumer.
Final: Ruling: UI/browser behavior deferred — no UI code changed and pilot feeds a later Web/offline plan — cost if wrong: future UI still needs single-session E2E/curl/screenshots before acceptance.
Final: Ruling: PMU/product SDK/UART/board claims stay unavailable — current evidence is a pinned relative QEMU model — cost if wrong: actual target overhead/calibration remains unknown.
Final: Ruling: cross-host runtime/offline closure not accepted — user removed target-platform validation and manifest lists missing host distributions/libraries/wheels — cost if wrong: intranet build must provision locked host dependencies separately.
Final: Ruling: repeat1 permits raw paired metrics only — no statistical stability claim or host overhead percentage — cost if wrong: three repeats and variance work remain later.
Final: Ruling: outer restore does not extract nested tar — archives are opaque regular bytes; executor will separately check nested source inventory in step6 — cost if wrong: this is not automatic build-ready workspace restoration.
Final: Ruling: ten baseline formatter failures remain reported — bytes unchanged and global Ruff plus changed format pass — cost if wrong: full-format debt persists.
Final: Ruling: pending final artifacts must be executed after review — report/package/restore/publication cannot be inferred from code audit — cost if wrong: Task8 cannot be marked complete without actual receipts.
