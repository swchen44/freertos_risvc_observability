# SDD ledger — plan: docs/plans/03-local-dashboard.md
Pre-flight: T1 query/export consumes Trace JSON and analyze intervals; use full schedule denominator, half-open window and int ticks.
Pre-flight: T2 store owns parsing and immutable raw bytes; T3 DataSource never decodes PSF or recalculates raw schedule.
Pre-flight: T3 charts consume bounded view aggregation, table queries remain raw and CSV remains complete.
Pre-flight: T4 browser tests use real HTTP/PSF and fixed local assets; no CDN required.
Ruling: Approved product spec takes precedence over prototype skill defaults requiring CDN/three variants/reapproval — use local ECharts SVG and confirmed layout, keep confirmation already granted by A — cost if wrong: visual direction can be adjusted from actual preview without changing data contract.
Task 1: complete (commits ebf62be..0b4e534, tests: .venv/bin/python -m unittest tests.unit.test_query tests.unit.test_export -v → OK)
Task 2: complete (commits 0b4e534..a48f48c, tests: .venv/bin/python -m unittest tests.unit.test_store tests.unit.test_server -v → OK)
Task 3: complete (commits a48f48c..a84eaf9, tests: npm --prefix web run test:unit → ℹ duration_ms 2078.807042)
Task 4: Ruling: Browser hang guard is 10 s assertions / 30 s large-capacity load / 60 s per scenario instead of the draft's 5 s action guard — the measured 100k upload/query needs over 10 s on this host, and no product performance threshold was specified — cost if wrong: future accepted latency target may require indexing or lower capacity limits.
Task 4: Source race reproduced RED (late run PSF replaced newer desktop upload); unified download/upload/saved-trace generation fixes it. API parsing remains real during held-response tests.
Task 4: T3 HTML/null/quality end-to-end checks completed in immediately following browser task rather than duplicating DOM mocks; BigInt/reset/late-response unit checks remained in T3.
Task 4: complete (commits a84eaf9..e5f2d3f, tests: .venv/bin/python -m unittest discover -s tests/unit -t . -v → OK)
Final review: fresh-context gpt-6-astra, range 1a29e50..e5f2d3f, Critical 0 / Important 3 / Minor 0; final verdict With fixes.
Final: Ruling: M4 implementation was declined by reviewer — user explicitly put it after M1-M3, retain planning-only status — cost: no cache improvement claim until the later model experiment.
Final: Ruling: physical cycles/cache/bus/UART overhead declined — QEMU icount cannot establish these, retain U tasks/M4 — cost: product performance numbers remain unknown pending platform evidence.
Final: Ruling: SMP/ring/other schemas/offline/cloud declined — keep explicit first-version exclusions — cost: POC cannot replace all Tracealyzer capabilities.
Final: fixed F01 signed Counter — test_signed_counter_matches_formatted_value_in_both_schemas RED→GREEN; full Python suite 96/96, JS 5/5, browser 11/11.
Final: fixed F02 missing unknown-window CSV — test_unknown_and_zero_windows_survive_metrics_csv RED→GREEN; full Python suite 96/96, JS 5/5, browser 11/11.
Final: fixed F03 undisclosed signal/request cap — test_signal_display_limit_has_explicit_scope and browser tail-anomaly test RED→GREEN; full Python suite 96/96, JS 5/5, browser 11/11.
Final: deferred minors: none.
Final: user requested local POC experiment/history, no merge or publishing; keep feat/psf-lab and designated checkout. No extra integration decision or remote operation introduced.
