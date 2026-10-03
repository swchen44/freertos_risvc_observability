# SDD ledger — plan: docs/plans/02-cases-and-analysis.md
Pre-flight: T1 analyzer consumes M1 semantic event ticks, actor_id and quality; known boundaries use COMPLETE marker.
Pre-flight: T2/T3/T4 oracle currently has fixed empty requests/phases; extend bounded RAM records and serialize at finish, preserving common fields.
Pre-flight: T4 suite consumes single-run clean checks; register only own output root and still require unchanged source fingerprints and no unrelated untracked files.
Ruling: Canonical case IDs follow approved M2 plan (inversion, inheritance, ordered_locks); replace unused runner allowlist aliases introduced in T5 — prevents case/config mismatch — cost if wrong: previously undocumented aliases no longer accepted; no runs used them.
Task 1: complete (commits c2b8cd8..1ba7c31, tests: .venv/bin/python -m unittest tests.unit.test_analysis -v → OK)
Task 2: complete (commits 1ba7c31..7578936, tests: .venv/bin/python -m unittest tests.unit.test_logger_assertions -v → OK)
Task 3: complete (commits 7578936..35121ca, tests: .venv/bin/python -m unittest tests.unit.test_inversion_assertions -v → OK)
Task 4: complete (commits 35121ca..ebf62be, tests: .venv/bin/python -m unittest tests.unit.test_deadlock_assertions tests.unit.test_suite tests.integration.test_case_suite -v → OK)
