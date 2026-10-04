# Z0 驗證紀錄

2026-10-04。正式 firmware／trace／packet 證據在 `runs/tcp-session-z0-v2/`，說明見 [Z0 報告](../../../docs/tcp-session-z0.md)。

| 檔案 | 結果 |
|---|---|
| `unit-only.log` | 133 個 unit tests 全部通過，包括 6 個新的 session oracle tests |
| `unittest.log` | 全套 139 個：136 通過，3 個既有 clean-tree integration tests 被未 commit 的工作目錄擋下 |
| `ruff-check.log` | 全庫 lint 通過 |
| `new-format.log` | 新增三個 Python 檔案的 format check 通過 |
| `ruff-format.log`／`all-format-summary.log` | 全庫 10 個既有檔案格式不符合；保存原始失敗，不修改無關檔案 |
| `verification.json` | 重新檢查 sources／artifacts hashes、重算三份 analysis，並檢查新增文件本機連結 |

先寫 `tests/unit/test_tcp_session.py`，第一次執行因尚無 `psf_lab.tcp_session` 模組失敗；建立 oracle 後 6 個案例通過。Firmware 經 QEMU 確認完整 packet transcript、buffer 回收與 lwIP 資源回到 baseline。沒有 mock QEMU 通過結果。

`v1` 為探索版；`v2` 加上 stack window markers，將測試 peer／封包保存的指令成本與協定區段分開。Cache replay 仍保留完整連續存取，沒有把被隱藏的 harness 存取偽裝為完整真實 cache 狀態。

此次未測新 UI，未修改既有 Dashboard，未執行 latency／time-control plugin。詳細限制及下一步見研究文件。
