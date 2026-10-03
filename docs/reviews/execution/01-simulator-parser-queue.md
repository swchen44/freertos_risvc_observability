# SDD ledger — plan: docs/plans/01-simulator-parser-queue.md

Execution: Native explicitly selected by user (A). Branch base 1a29e50.
Ruling: Work in the user-designated dedicated poc checkout on feat/psf-lab; do not create a second nested checkout — preserves requested canonical folder — cost if wrong: less parallel workspace isolation, mitigated by dedicated repository and clean source checks.
Pre-flight: T1 provenance → T4 build → T5 run: locked source and tool hashes; consistent.
Pre-flight: T2 binary → T3 semantics → T5 harness: common JSON v1; actor_id and object_id distinct, ticks relative to origin.
Pre-flight: T4 capture → T5 oracle: direct single stream, completion before close, independent oracle; consistent.
Ruling: Normalize plan task headings to Task N: Pn-Tn for supplied task-start tooling — no scope change — cost if wrong: documentation anchors change, no existing anchor links.
Task 1: in_progress.

Task 1: 7 unit tests GREEN; Ruff check/format pass. Tool downloads still running; not complete.
Ruling: Work on independent T2 while T1 downloads run — README dependency graph explicitly permits it — cost if wrong: parser regression may need adjustment when RV32 fixtures arrive.

Task 1: Ruling: Ruff installed version 0.16.10 formats Markdown fences; exclude docs so Python checks do not rewrite research snippets — cost if wrong: prose code snippets not autoformatted, actual Python still checked.
Task 1: Ruling: git submodule add --branch cannot use this tag as remote branch; fetch exact pinned commit and add the already-cloned repo — cost if wrong: rejected by explicit commit check.
Task 2: complete (commits 1a29e50..56396f8, tests: .venv/bin/python -m unittest discover -s tests/unit -t . -v → OK)
Task 3: complete (commits 56396f8..5cab0f3, tests: .venv/bin/python -m unittest discover -s tests/unit -t . -v → OK)
Task 1: complete (commits 1a29e50..5d333c5, tests: .venv/bin/python -m unittest tests.unit.test_doctor tests.unit.test_provenance -v → OK)
Task 4: Ruling: SDK direct event commit ignores short byte counts and raw header retries TRC_FAIL forever; adapter must write-all with bounded progress and fail-fast finisher on permanent I/O error — prevents silently corrupt PSF or retry hang — cost if wrong: failed capture may have no oracle; host preserves partial bytes and nonzero exit.
Task 4: Ruling: Keep SDK-created TzCtrl task and document its priority 1 / 10-tick delay; disabling stack monitor does not suppress creation in this version — no SDK patch — cost: this observer task contributes trace activity.
Task 4: complete (commits 5d333c5..94f2a53, tests: .venv/bin/python -m unittest tests.integration.test_clock_capture -v → OK)
Task 5: complete (commits 94f2a53..c2b8cd8, tests: .venv/bin/python -m unittest discover -s tests -t . -v → OK)
