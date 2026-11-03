# 執行決策與代價

依序保留全部Ruling。pending屬決策當時狀態；正式package／source extraction已完成，發布以receipt為準。

1. Ruling: 使用既有 ~/git/percepio/poc 與 feat/psf-lab 分支，工作不移出使用者指定位置；不新增 worktree — 使用者指定 POC 為所有實驗與文件位置且目前乾淨 — 若有同時寫入需停止排查，不能覆蓋他人工作。

2. Ruling: wire fixes exact clock_domains names, phase values and epoch old_value/new_value; request/marker/MMIO records include pc — spec requires preserving observed PC and strict per-kind schema, plan left key spellings open — cost if wrong: coordinated producer/consumer schema change before captures.

3. Ruling: add an unmodified pinned upstream QEMU symbol-generator fixture with license/provenance in references/qemu-clock-anchor — export tests must execute the real generator without a new network dependency — cost if wrong: fixture must be refreshed when the pinned QEMU version changes.

4. Ruling: patch generator accepts sparse edited trees and only nine named paths; omitted paths are unchanged, deletion unsupported — avoid another 817MiB source copy on a disk with 5.3GiB free — cost if wrong: future deletions require a new explicit interface.

5. Ruling: private core header selects qemu/poc-clock-anchor-api.h only under POC_CLOCK_IN_QEMU; Meson defines that flag without adding include/qemu globally — fixes header shadowing while keeping one byte-identical canonical core — cost if wrong: rebuild and native dual-include test fail; first build retained.

6. Task 5: Ruling: clock_anchor_init accepts (config_path, handle, begin_pc, end_pc) — existing collector already owns the unique time-control handle and capture boundary PCs, absent from the proposed clock config; pass them explicitly instead of a second ownership request or extra mutable setters — cost if wrong: coordinated internal signature update; public QEMU ABI unchanged.

7. Ruling: lossless gzip after each capture, verify decompressed SHA before deleting only its uncompressed duplicate — preserve every raw/context/clock record within disk budget after user-approved cleanup — cost if wrong: explicit gzip read support required in validator/restore; compressed and content SHA both recorded.

8. Ruling: iter_clock_records adds optional content_hasher to hash bytes actually consumed in each scan — pre/post whole-file checks alone cannot detect a temporary swap during parsing — cost if wrong: additive reader argument must remain backward compatible; plain/gzip test compares exact uncompressed SHA. Mode0 consumes pass2 even without anchors.

9. Ruling: valid native evidence with missing/nonunique SDK candidate returns alignment unavailable and all rows unknown, rather than evidence invalid — matches spec6's distinct evidence/alignment axes — cost if wrong: smoke still must reject absent verified-bounds, so this cannot silently pass pilot.

10. Ruling: full stage independently revalidates the four smoke captures before expansion, then keeps fresh validation results in memory for final comparisons instead of replaying all new runs twice — enforces the approved causal gate and avoids redundant scans — cost if wrong: final source/tools and frozen-smoke file checks remain mandatory; independent report generation revalidates every run again.

11. Ruling: nested source snapshots are opaque regular tar.gz bytes inside per-file gzip package; their upstream symlink metadata is preserved but never extracted by outer restore — satisfies complete-source retention while outer members reject symlinks/traversal — cost if wrong: source extraction needs a separate inventory-checked step, not an implicit build-ready claim.

12. Ruling: restore spools one verified concatenated gzip to a temporary file, then streams decompression in64KiB chunks — simple bounded memory and explicit per-part/full-content checks — cost if wrong: restore disk headroom includes largest gzip entry in addition to all original bytes.

13. Ruling: host GCC distribution, GLib/system libraries and complete offline wheels are not bundled; manifest records locks and offline_rebuild unavailable — approved plan explicitly allows missing offline dependencies and no cross-host target exists — cost if wrong: intranet build requires separately provisioning these pinned host dependencies; data/source restoration remains testable.

14. Ruling: global format gate retains10 unchanged baseline failures, verified byte-identical to9c3c9aef; full Ruff check and changed-file format must pass — preserve historical source/provenance and spec requires Ruff rather than rewriting old model files — cost if wrong: global formatting debt remains explicit, never reported passed.

15. Ruling: rebuild accepted tools into new initfix directory after collector dependency change, with one final ELF per candidate reused by all sixteen captures — old tools hash must fail after C changes and old evidence stays preserved — cost if wrong: new build/ELF identities must be recorded; earlier development bounds are not exact IRQ attribution or formal acceptance.

16. Final: Ruling: UI/browser behavior deferred — no UI code changed and pilot feeds a later Web/offline plan — cost if wrong: future UI still needs single-session E2E/curl/screenshots before acceptance.

17. Final: Ruling: PMU/product SDK/UART/board claims stay unavailable — current evidence is a pinned relative QEMU model — cost if wrong: actual target overhead/calibration remains unknown.

18. Final: Ruling: cross-host runtime/offline closure not accepted — user removed target-platform validation and manifest lists missing host distributions/libraries/wheels — cost if wrong: intranet build must provision locked host dependencies separately.

19. Final: Ruling: repeat1 permits raw paired metrics only — no statistical stability claim or host overhead percentage — cost if wrong: three repeats and variance work remain later.

20. Final: Ruling: outer restore does not extract nested tar — archives are opaque regular bytes; executor will separately check nested source inventory in step6 — cost if wrong: this is not automatic build-ready workspace restoration.

21. Final: Ruling: ten baseline formatter failures remain reported — bytes unchanged and global Ruff plus changed format pass — cost if wrong: full-format debt persists.

22. Final: Ruling: pending final artifacts must be executed after review — report/package/restore/publication cannot be inferred from code audit — cost if wrong: Task8 cannot be marked complete without actual receipts.

23. Ruling: publish a labelled preview omitting41 large streams/history archive while retaining every byte in complete restore parts; relocate package rather than duplicate it — keeps disk and Git payload bounded with no data loss — cost if wrong: preview alone is not a validator input; consumers must restore full runset first.

24. Ruling: retain this plan workspace and publish relevant logs rather than delete intermediate evidence at skill finish — user explicitly requested process/intermediates for intranet restoration — cost if wrong: retained local/repository evidence consumes storage.

25. Ruling: narrow .gitattributes exceptions preserve generated CSV CRLF, linker map and size output whitespace without editing captured bytes — git diff --check initially flagged434 native-output lines; authored docs remain checked — cost if wrong: whitespace style is intentionally not enforced on these immutable evidence formats.

Deferred minors：無。
