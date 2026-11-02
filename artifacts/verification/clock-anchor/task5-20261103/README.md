# C2b Task 5：TCP collector 與實際 capture

2026-11-03，來源 `1bba920ce00ef2b18fe39da72a2a26586f0d82f8`。12 個新增測試通過；完整 suite 執行 364 個，362 通過、2 個 opt-in runtime skip。另明確啟用 guest runtime 的 2 個測試通過，無 skip。Ruff check 與本輪 7 個 Python 檔 format 通過；全庫既有 10 個 format 問題仍保留。

baseline／pbuf 各編譯一次 ELF；legacy collector 從鎖定 commit 唯讀匯出，新 collector 使用 opt-in hooks。QEMU canonical overlays、編譯來源與依賴 hash 都核對，full resume 前須檢查 smoke 檔案是否變動。

第一份 development O capture 正常退出：431,823 筆 raw access、1,109,492 model cycles、431,823 組 request／applied、5 組 marker、78 組 device／plugin MMIO；footer pending 0。QEMU host wall 約 2.010 秒，這是單次觀測值。

**尚未完成因果與 PSF join 驗證。** 以上是檔案及 collector 結果，不代表時間對齊已成立；正式 16-run 仍為 0。Task6 負責獨立 replay、FIFO／公式及 bounds；Task7 負責透明性比較。

- `tools.tar.gz`：兩份候選的 ELF／map／symbols／build logs、新舊 plugin、匯出的 legacy sources、tools manifest。
- `development-O.tar.gz`：完整 PSF、packets、oracle、raw／context／clock gzip 與 capture receipt。
- `inventory.json`：上述檔案與測試 logs 的大小、SHA256。
- `progress-ledger.md`：本輪決策與歷史失敗紀錄。

raw／context／clock 逐檔無損 gzip，刪除未壓縮副本前已重新解壓核對內容 SHA；manifest 同時保留原內容與 gzip identity。解開 tar 到新目錄即可檢視，manifest 中原絕對路徑是 provenance；檔案驗證須使用還原目錄的相對檔名。完整 QEMU source／binary 與分卷還原由 Task8 交付。
