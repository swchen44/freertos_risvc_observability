# M4.2／M4.3：可重現的 data cache 相對比較

2026-10-04。沿用使用者已確認的相對最佳化目的。先完成資料存取重播，instruction cache 與 task 級對時保留後續。

## 設計與邊界

RV32 FreeRTOS 用相同 64×64 uint32 矩陣，比較 row-major／column-major 兩種兩輪加一操作；volatile 保留實際 load/store。輸入為 0..4095，最終 checksum 必須為 8,394,752。QEMU plugin 只擷取 workload 函式 PC 範圍內、矩陣地址範圍內的 guest physical data 存取，排除初始化及 IRQ 的其他資料。

Python 以 cold、LRU、write-allocate、單 core 的 L1D + data-only L2 tag 模型重播。每個跨 line 存取拆成多個 line lookup。read/write 各自計數；不模擬 dirty/writeback、prefetch、DMA、bus 或 timing。L2 分母是 L1 misses。這是資料工作集模型，不能稱為完整 unified L2 CPU 模型。

## 檔案責任與驗收

- `third_party/qemu-cache/`：原始官方 cache.c、API header、授權與 hash，供內網還原。
- `tools/cache/addresses.c`：有界 guest 位址擷取器；只支援單 core，完成時核對輸出數量。
- `firmware/app/cases/cache_row.c`／`cache_column.c`／`cache_workload.h`：相同工作量與 checksum 的兩種遍歷。
- `src/psf_lab/cache_model.py`：驗證 geometry、LRU replay 與 JSON 統計。
- `tests/unit/test_cache_model.py`：cold/warm、容量/set conflict、LRU、跨 line、read/write、無 L2、空資料與無效輸入。
- `tools/cache/run.py`：建置、3 次／variant、PSF／oracle／CSV 收集、模型敏感度比較、hash manifest。外部指令錯誤必須中止。
- `runs/cache-relative-v3/`：保存每輪 ELF、map、PSF、oracle、存取 CSV、分析 JSON 與 logs。
- `docs/cache-replay.md`：還原步驟、實際結果、限制與下一步。

## 順序

- [x] 先寫 unittest 並觀察失敗；實作 cache model，再跑 unittest／Ruff。
- [x] 建置 guest address plugin；建置兩個 firmware。
- [x] 每個 variant 三次獨立 QEMU capture；核對 checksum、事件數、guest return code。
- [x] 使用 1／4／16 KiB L1D、32 KiB L2、64-byte line、4-way LRU 重播；固定輸入、比較 read/write miss。
- [x] 保存 source、license、設定、PSF、ELF、map、raw CSV、manifest、測試與重建命令。所有紀錄只含模型內結果。
- [x] 更新 README／M4 checklist、核對 hash、commit、push，確認遠端一致。

後續 Dashboard 將消費這份版本化 JSON；本輪不以 raw CSV 順序推算 PSF tick，也不宣稱 task 級 cache 對時完成。


追加需求：研究 cache 空間使用效率、PSF counter 接入方式與兩種 Dashboard。已加入 per-residency byte-use 指標、PSF hash sidecar、Web／離線 cache 工作區、PolyBenchC 來源快照；研究與未完成事項見 `docs/research/Cache效率與PSF擴充.md`。PSF counter bridge、L1I 與任意 source 熱點尚未實作。

Code review 的三項重要問題已處理：重播驗 hash、case 身分交叉核對、capture／analysis source receipt 分離。先觀察 swapped-case regression test 失敗，再修正至通過。執行完整 integration 需要乾淨 commit，最終證據以 `artifacts/verification/cache-replay/completion.json` 為準。
