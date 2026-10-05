# A 執行紀錄

計畫：docs/plans/11-next-cache-research.md；使用者已回覆 OK。順序 A → B → C，本輪完成 A。

Ruling: 沿用使用者指定的 poc/ 與既有 feat/psf-lab feature checkout；不另複製大型 source/toolchain/capture。起點 root 5d40558、POC 7b4e16d，均乾淨。

Pre-flight: A1 workload contract 由 A2 runner/guest 及 A3 oracle 消費；新增 keyword-only workload 保留舊 API。A4 僅呈現 A3 驗證過的同 workload 比較，不跨組計算分母。

- A1: 完成，與 runner/legacy 共16個 targeted tests 通過。
- A2: 已完成。首次2次失敗 probe保留；修正後4次成功 probe；96 次正式 capture 通過。
- A3: 已完成 96 份 raw digest/PSF/封包核對、16 份詳細 replay；三次結果一致。
- A4: Web/offline agent-browser + curl 已通過，24列比較，10張截圖。

Ruling: 正式捕捉輸出目錄暫列本 repo info/exclude，避免前一組 artifacts 使下一組 clean-source gate 失敗；結束時 force-add 所有成果，來源本身每組仍要求 clean。輸出目錄保留原路徑，不搬移造成 manifest path 失效。

Ruling: A08 首次探針觸發 pending ACK assertion。移除 plugin 並開 UART 診斷確認 guest assertion line 277；lwIP tcp_recved 的 receive-window update 可立即 ACK。新 matrix peer 消費最多一個正確 ACK，host oracle 檢查 seq/ack/flags/empty payload，舊 API 不放寬。新增正/負測試先紅後綠；不改 IRQ guard。


Review：獨立 reviewer 檢查 A source 與 UI，指出 plugin/hash map completeness、同組 workload equality、dashboard source pin completeness，以及批次 sibling logs ignore。均已修正並新增負向測試。未改正式 capture 的來源檔案。

分析時發現 checksum compile command 含重複 `-Os -Os`；原檢查誤以為只能出現一次。修正為所有 optimization flags 的集合必須恰為 `{-Os}`，不接受其他 optimization level。

驗證：全 repo Ruff check 通過。本輪變更 Python format check 通過；全 repo format check 有10個既存檔案差異，未修改已釘選的歷史 source。文件606個本地連結、422個baseline hashes通過。

正式擷取 source commit：6a0ef47；正式 driver wall time 保留於 logs/percepio-matrix-execution.json；原始失敗輸出與 TDD red/green 也保存。最終回歸數量及 tested commit 以 completion.json 為準。

首次 full regression 251 tests有3 errors：並行舊UI產物使2個clean-tree integration拒絕；batch unit test的macOS symlink temp path錯配造成1 error。保留失敗log；恢復原歷史UI產物、另外保存本輪結果、resolve測試root後，改成單獨完整重跑。
