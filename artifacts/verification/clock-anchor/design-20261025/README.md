# C2b 方案 A：書面設計 checkpoint

日期：2026-10-25。**使用者已選A；書面規格完成待審閱。沒有build、guest執行、新capture、unittest或browser runtime驗收。** 這個checkpoint不能當成pilot成功。

| 檔案 | 內容 |
|---|---|
| `decision.json` | 使用者原訊息A、已選修改範圍、待審閱狀態；5筆markers與16-run是提出的設計數字，尚未執行 |
| `source-audit.json` | parent commit、10個本機來源hash、現有QEMU與A02身分核對；排除的loader方案與採semihosting的理由 |
| `upstream-source-check.json` | 固定QEMU revision的CLI／semihosting三份官方來源重取與逐byte核對，使用正常TLS驗證 |
| `self-review.json` | 規格一致性自審、source研究發現與修正；不宣稱whole-code或runtime review |
| `docs-check.json` | Markdown連結／圖片及baseline來源hash檢查 |
| `inventory.json` | 此資料夾其他各檔的大小與SHA-256 |

規格在`docs/design/c2b-clock-anchor-pilot-v1.md`；狀態與checklist在`docs/plans/19-c2b-clock-anchor-pilot.md`。規格分開request／applied／app sample／PSF TS，明訂same-ELF對照、epoch／unknown、串流容量限制、原始資料與還原保存方式。

來源盤點提前排除「Generic Loader改ELF內rodata mode」：QEMU之後的rom_reset可覆寫該值。這是source-derived失效路徑，本輪沒有執行失敗的guest。直接RAM slot另有PT_LOAD／startup／DTB範圍問題，因此本版採既有semihosting cmdline，在capture之前讀取與驗證；新operation仍須capability smoke。

2026-10-23的source-only收據原樣保留，當時A／B pending是歷史狀態；本次decision記錄使用者已選A。尚未完成的實作計畫、QEMU／firmware改動、pilot／誤差報告、Web／offline接合與知識庫增補，不能因本checkpoint存在而勾成完成。
