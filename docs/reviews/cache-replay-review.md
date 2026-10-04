# Cache replay review

2026-10-04。獨立 reviewer `/root/cache_review` 審查本輪 model、capture、provenance、Web／offline、package 與 tests。

## 發現與修正

1. CLI replay-only 原先接受被截斷 CSV：改成與 Web 共用完整 evidence 驗證，全部通過才寫衍生分析。
2. 目錄名稱可把 row／column 標反：新增 six expected cases、manifest variant／repeat、oracle case_id 交叉核對。`test_swapped_case_directories_rejected` 先失敗再修正通過。
3. 原 capture 與新 analysis source hash 混淆：新增每筆 model SHA-256 與獨立 analysis receipt。正式 v3 重新執行六次 capture，保存當時 source hashes。

Reviewer 再查確認三項重要問題均修正，16 個 cache tests 通過，v3 suite source 與 analysis receipt hashes 一致；未發現新的重要問題。Reviewer 未重跑瀏覽器與 restore archive。

## 實際 E2E 額外發現

離線資料比 Web API 快，Tabulator 未建好就 setData，產生 `verticalFillMode` null 錯誤。加入 tableBuilt Promise 後，offline 真實 E2E 通過。Web／offline 都驗證篩選、SVG、來源詳情、CSV 筆數／數值／排序及 browser errors，並保存截圖。

第一次 full Python integration 因未提交的 source 被既有 clean-tree guard 拒絕；保留 precommit log。正式驗收在 source commit 後重新執行，不以該次失敗當通過。

完成狀態以 `artifacts/verification/cache-replay/completion.json` 與各原始 log 為準。
