# C1 獨立審查與處理

Reviewer: c1_whole_review。範圍：ff0f953 至 1baf3c2 的核心程式、後續 UI 驗收腳本；未修改檔案或執行 QEMU。審查執行 11 項 scoped Python、2 項 Node 測試通過。

## 已修正

1. Important：context／function filter 更新後 PC table 保留舊成本。真實 agent-browser RED 重現空篩選仍有 PC；render 清除明細後 GREEN。證據在 pilot/stale-red、pilot/stale-green。
2. Important：hash 正確的 malformed bundle 可回 200／404／500。增加 catalog/bundle 結構、run identity、成本守恆、derived pairing 和 manifest 重建驗證；未知 ID 獨立 exception 為404，無效資料503。RED/GREEN logs保留。
3. 原評 Minor 的 unmatched／ambiguous 只有總數，依設計需求提升為必須完成：每列加 pair_status、pair_reason、delta/percent；Node RED/GREEN 通過，CSV同步。

## 延後的 Minor

- B2 evidence 的 raw_stream_sha256 來自 pinned A stream；formal loader 另以 formal_record.audit.stream_sha256 驗證實際 raw stream。目前保存的對照一致，沒有觀察到數值錯誤；後續可直接使用 formal 欄位以減少誤解。
- 過期 fetch 的成功有 generation guard，失敗未設相同 guard；快速切 workload 若舊請求延遲失敗，可清除新頁面並顯示載入錯誤。重新選 workload 可恢復；未發現把不同 run 數值合併的情況。

UI / 全回歸 / 正式報告數量以 completion.json 為準，審查不代替測試。

## 最終畫面檢查補修

PC 表誤帶函式配對欄位，已用 agent-browser 新增三欄斷言先重現 RED，再移除不適用欄位。重新建置全部 8 份 HTML，Web／offline 重新通過；失敗保存 pilot/pc-columns-red，最終證據為 ui/server 與 ui/offline。
