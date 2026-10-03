# 獨立整體 Code Review

範圍：`1a29e507aef7db1d7ceae6b3891e0f0a1fec654b` → `e5f2d3fd0490398e066e459c2f7e30f506b5590d`。Reviewer：獨立、無先前實作對話的 `gpt-6-astra` agent，唯讀檢查三份計畫、spec、ledgers、來源、測試與證據；未改工作目錄、未建立下層 agent。

## 初次判定

**With fixes**。Critical 0、Important 3、Minor 0。Parser schema 分離、原始證據與 hash、獨立 oracle、相同 workload 的 A/B、完整 CSV／SVG／過期請求控制均符合主要方向。仍有下列具體邊界錯誤。

| ID | 已重現問題 | 修正 | 直接回歸驗證 |
|---|---|---|---|
| F01 | `Counter: %d` 的 raw `0xffffffff` 顯示文字 -1，但 signal 值為 4294967295 | 依已解碼的 schema-width signed message 取得 Counter，保留 raw arguments | 32／64-bit 的 -1、最小負數、0、正數；message／counter 必須一致 |
| F02 | 全 unknown 的 100-tick 窗口匯出 metrics CSV 只有 header | 無 task share 時保留一列窗口摘要；task／fraction 留空 | 全 unknown、範圍外窗口、空 trace，known／unknown／window 不遺漏 |
| F03 | 超過 2,000 signal／request 只回傳前段，UI 卻只寫完整總量 | API `display_limits`、UI 呈現／總量、資料點起訖、縮小窗口提示 | 2,001 個 Counter，尾端 999999 異常；圖明示只呈現前 2,000，完整 CSV 仍包含最後異常；requests cap 另測 |

三項都先用新增測試重現 RED，再修改產品程式。記錄見 [unit RED](../../artifacts/verification/review-red.log)、[browser RED](../../artifacts/verification/review-browser-red.log)。修正後的完整驗證結果以 README 與最後 GREEN logs 為準。

Reviewer 自行重跑原有 87 unit、5 JavaScript tests 與 Ruff，核對 21-run／9-comparison index；未另外重跑 QEMU／Playwright。主 agent 的最終驗證補回完整測試，依流程不再請第二位 reviewer 重看相同修正，不能宣稱做過第二次獨立 review。

## Declined to judge 與執行者裁定

| Reviewer 未判定事項 | 裁定 | 代價／後續 |
|---|---|---|
| M4 cache 相對最佳化的實作品質 | 使用者明定排後面，本次只驗設計計畫已保留目的與邊界 | 不能從本 POC 宣稱已有 cache 改善或模型校準；依 M4 再驗 |
| 實體 cycles、cache／bus、UART overhead | 保留為 U 任務與 M4；QEMU icount 不可作實體效能證據 | 產品 CPU／IRQ／bandwidth 數字仍未知，需原始碼與硬體 |
| SMP、ring dump、其他 schema、離線 HTML、雲端 | 明確不在第一版本機 PSF 流程，維持分期 | 使用者不能將此 POC 當完整 Tracealyzer 替代品；缺少的能力仍列 handoff |

其他 observations：SDK 設定註解與既有 patch context 有尾端空白，reviewer 沒有判成產品缺陷，未為此改動 SDK／patch。沒有延後的功能性 Minor。


## 修正後結果

修正 commit `5f84e53`，90 unit＋6 integration 合計 96／96、5／5 JavaScript、11／11 Playwright 通過。Clock probe 在最終整合前重新建置；最新正式 21-run 證據也由修正後 decoder 重驗。完整 [Python log](../../artifacts/verification/all-tests-final.log)、[browser log](../../artifacts/verification/browser-tests.log)、[unit GREEN](../../artifacts/verification/review-green.log) 已保存。未留下 Critical／Important 待修項目；沒有延後的功能性 Minor。
