# C2a timing follow-up · 2026-10-23

Overall acceptance: **partial**. All data remain the A02 pilot14. Formal40/8HTML were not generated.

| Trial | Ready s | Filter s | Peak RSS MiB | Overall |
|---|---:|---:|---:|---|
| offline-number-2 | 5.740 | 3.407 | 390.19 | True |
| offline-number-3 | 5.244 | 3.500 | 423.75 | True |
| offline-number-full | 4.522 | 2.849 | 536.05 | True |
| server-1 | 16.834 | 5.291 | 330.70 | False |
| server-2 | 11.780 | 3.048 | 422.27 | True |
| server-3 | 16.814 | 3.640 | 382.38 | True |
| server-api-fix | 13.150 | 3.959 | 436.97 | True |
| server-number-1 | 21.357 | 3.710 | 378.67 | True |
| server-number-2 | 16.112 | 3.143 | 471.80 | True |
| server-number-full | 11.759 | 2.916 | 650.36 | False |

All receipt-listed sessions closed with no remaining owned browser PIDs. Sampling interval 0.2 s; transient peaks may be missed. Web curl route results are saved in each Web trial. Offline trials required server unavailable and HTTP/HTTPS blocked.

## Files

- `A02-final.html`: final 16e0cbc pilot, standalone offline. Adjacent receipt records assets/source hashes.
- `A02.html`: intermediate 2ceb3ec export retained.
- `server-number-full/`, `offline-number-full/`: full interaction receipts, screenshots, complete compressed CSV and cross-chunk CSV.
- `server-1/`: preserved timing failure before canonical integer fast path.
- `*.prof`, `*.cpuprofile`, `before.txt`, `after.txt`: profiling evidence, not HTTP latency or target firmware benchmarks.
- `number-pairs.json`: paired full-query Node measurements.
- `equivalence.json`, `result-*.json`: complete A02 query exact equality.
- `rss-stage-summary.json`: Web full export peak, no causal allocation attribution yet.
- `review.md`: independent read-only review and resolved minor.
- `python-full.log`, `node-final.log`, `ruff.log`, `build-final.log`: verification logs.

## Restore

Open `A02-final.html` directly. For Web pilot data use the existing `../checkpoint-20261013/pilot.tar.gz` and its documented restore procedure; do not overwrite an existing dataset. Build the current web bundle and serve from POC. `formal/` remains only a serving path for pilot14.

Next: profile CSV production/transfer/Blob/download stages, retain complete data and cancellation, then revalidate RSS640/ready25/filter5. Only after acceptance generate formal40 and 8HTML; A08/C1/Playwright final regressions remain pending.
