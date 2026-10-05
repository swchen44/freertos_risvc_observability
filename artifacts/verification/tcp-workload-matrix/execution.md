# A 執行紀錄

計畫：docs/plans/11-next-cache-research.md；使用者已回覆 OK。順序 A → B → C，本輪完成 A。

Ruling: 沿用使用者指定的 poc/ 與既有 feat/psf-lab feature checkout；不另複製大型 source/toolchain/capture。起點 root 5d40558、POC 7b4e16d，均乾淨。

Pre-flight: A1 workload contract 由 A2 runner/guest 及 A3 oracle 消費；新增 keyword-only workload 保留舊 API。A4 僅呈現 A3 驗證過的同 workload 比較，不跨組計算分母。

- A1: 完成，與 runner/legacy 共16個 targeted tests 通過。
- A2: guest/runner已擴充，待實際探索。
- A3: 未開始。
- A4: 未開始。

Ruling: 正式捕捉輸出目錄暫列本 repo info/exclude，避免前一組 artifacts 使下一組 clean-source gate 失敗；結束時 force-add 所有成果，來源本身每組仍要求 clean。輸出目錄保留原路徑，不搬移造成 manifest path 失效。
