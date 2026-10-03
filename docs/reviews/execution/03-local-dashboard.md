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
