# T1 memory-service 驗證

2026-10-04。新功能以 `test_memory_timing.py`／`test_timing_report.py` 先定義手算與完整性期望，首次執行因新模組尚未存在失敗，實作後新增 14 個測試通過。

- `unit-tests.log`：147 個 unit tests 通過。
- `ruff.log`：全庫 lint 通過。
- `format.log`：本次四個 Python 檔案的 format check 通過。
- `replay-check.json`：驗證來源／輸出 hashes、三份 Z0 capture 重播一致、RAM 延遲敏感度、300 列 CSV 加總與文件連結。
- 正式產物：`runs/timing-z0-v2/`，保留所有 profile、trace hashes、source hashes 與假設。

現有全庫格式檢查的 10 個既有檔案問題仍在 Z0 驗證目錄記錄，本次沒有改寫無關檔案。沒有新增 Web UI，因此不宣稱完成新的 browser E2E 或 Dashboard。

本版 T1 為離線成本估算，未執行 T2 的 guest time-control 實驗。
