# C2a CSV 記憶體研究與重新驗收

原 Web 超限650.36MiB的歷史收據保持在 timing-20261023。診斷原版445248KiB、UTF-8 transfer452560KiB，沒有證明改善，產品改動已還原。兩者CSV為74118680 bytes，SHA-256完全一致。peak在下載click後約0.3s，未證明leak或固定allocation原因。page heap粗粒度值不代表Worker/程序全部記憶體。

隨後預先固定3次未插樁完整Web驗收，全部通過；receipts與screenshots保留。三次是cbdfc3d harness，只代表原版容量與原有操作；後加的函式CSV oracle／空圖assertions另由正式候選full receipt驗證。所有owned sessions都close且無殘留PID。

- `baseline-profile/`、`transfer-profile/`：診斷收據、source快照與CSV。舊probe的characters欄位對text為UTF-16長度、對buffer為UTF-8 bytes；勿直接當同一Unicode單位比較。本案例輸出是ASCII，CSV byte hash相同。兩次源碼為working-tree實驗，附source-provenance。
- `transfer-profile/source/web/`：已撤回的完整transport模組與測試。可在該目錄執行Node測試；不屬於目前產品。
- `csv-equivalence.json`、`comparison.json`、`product-equivalence.json`：CSV hash、RSS階段與原版bundle恢復證據。
- `repeat-1/2/3/`：預先固定的完整重測，daemon重啟後核對receipt繼續，未重複第一輪。
- `capabilities/`：分別缺Worker／DecompressionStream的真browser fixture；不是實際平台缺功能回報。
- `playwright/`：11/11單worker回歸；歷史tracked results/capacity已保存後還原。
- `python-dirty-precondition-failed.log`：323項中的3個integration因來源未commit而中止。commit後完整重跑323通過，見`python-clean323.log`。
- `transport-green-trial24.log`是含已撤回實驗的24項；目前產品Node suite是23項，見`node23.log`。
- `formal-build.log`：40份新生成，每份與C1完整facts/totals比較；正式資料另在相鄰formal/，舊serving pilot保留於artifacts/local，已發布pilot.tar.gz仍可復原。

此目錄記錄當時checkpoint，正式40／8HTML最終browser驗收尚由後續收據決定。

## 串流實驗前的8HTML

`history/offline-before-http-stream/*.html.gz`保存全部8份第一候選，解壓後與相鄰receipt的原SHA核對。這不是最終stream候選。`transfer-profile/source/web/package.json`是後加的Node模組測試wrapper，供內網重跑transport測試，不是原產品更動。
