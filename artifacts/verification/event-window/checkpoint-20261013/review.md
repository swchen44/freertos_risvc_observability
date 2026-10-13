# Review 與有效證據邊界

來源程式修正 commit：0584229。獨立 reviewer c2a_whole_review。

4項產品 Important 均已修正並複查：取消manifest loader／舊run資料；CSV全量字串暫存；dictionary型別驗證；壞deflate轉ValueError。Minor source mapping、CSV control prefix與render token guard也已處理。

驗收腳本另外發現3項 Important：同一eval切run可能只fetch A、cleanup只取啟動PID快照、取消可能發生在匯出完成後。修正後以pending B→完成A→release B、持續追蹤PID、原子檢查0<progress<1後取消並核對無新下載驗證。第2次獨立複查未見新的Important。

## 不採認與保留的紀錄

- ui/c2a-lifecycle-browser-1：原passed保留，但因上述harness問題，不作為最終生命週期證據。有效替代為ui/c2a-lifecycle-browser-2。
- ui/c2a-e2e-reviewed-offline-3與server-2：hover、實際drag、43萬列CSV與篩選表格操作有效；當時export_cancel_retry不足以單獨證明inflight取消，改由lifecycle-browser-2補證。整體RSS均超過512MiB，因此passed仍false。
- ui/c2a-capacity-viewport-server-1至3：只代表初次load／完整filter的capacity範圍，不代表完整多操作流程。
- ui/c2a-capacity-viewport-offline-2：RSS超限，未執行第3次。其他早期capacity資料只供診斷，不取代此結果。
- ui/c2a-intentional-failure-close：刻意失敗；close_exit=0與無殘留PID才是該測試要核對的結果。

容量門檻保持512MiB，正式40／8HTML未產生。所有scope與不足都保留，不能將此checkpoint解讀為正式驗收完成。
