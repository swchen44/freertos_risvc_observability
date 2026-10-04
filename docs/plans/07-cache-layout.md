# Cache layout：AoS／SoA／hot-cold 實驗

> 狀態：草稿與 firmware 範例已保存；使用者新增 TCP/IP 優先需求，暫緩執行。本案例尚未編譯、擷取、Dashboard 整合或驗收，不可視為已完成。

2026-10-04，延續使用者 go 授權的 cache 相對最佳化工作。這是既有 capture/replay/UI 的擴充，不改變 data-only LRU 模型。

## 設計

256 records，每筆 16 個 uint32 欄位，總配置 16 KiB。兩個 hot 欄位初始化為 i、3i，另外 14 個 cold 欄位保留同一可驗算資料。workload 對兩個 hot 欄位各加一、共兩輪。最終 hot checksum = 131584；逐欄檢查 cold 未改變。AoS / SoA / hot-cold 三種配置各擷取三次。預期每次 1024 reads + 1024 writes；相同 logical work，hot bytes 共 2048。

Plugin 仍只收 workload PC 範圍中的 data region 存取。排除初始化與驗算，cold start replay；本輪不含 instructions／writeback／prefetch。明確區分 allocation footprint、hot footprint 與已觀測 bytes。

## 檔案與驗收

- [ ] `cache_suites.py`：固定 matrix／layout 契約，沿用 matrix legacy manifest，未知 suite 拒絕；unittest 先失敗再實作。
- [ ] `cache_report.py`／`tools/cache/run.py`：參數化 variants／checksum／symbol／counts，所有案例驗 hash／身份／cold oracle；不弱化舊驗證。保存 compiler、source、symbols、raw CSV、PSF、ELF。
- [ ] `firmware/app/cases/cache_layout.h` 及三個 wrapper：同工作量；各三次，counter 與獨立手算預期一致。
- [ ] Web／HTML：實驗選擇器、動態 workload 卡片、比較時限同一實驗、CSV／來源證據；既有 matrix 能用。
- [ ] agent-browser Web／offline E2E、curl integration、Python unittest／Ruff、既有 Node／browser regression。
- [ ] 更新研究與 README 截圖、還原包；乾淨目錄重播與重新模擬；code review、commit／push／遠端 hash 核對。

## 可否證預期

64-byte line、4-way LRU。AoS 的每條 line 僅 8 hot bytes，所以模型內使用比例 12.5%；4 KiB L1 下 512 misses。SoA／hot-cold 將 hot bytes 集中為 2 KiB，在 4 KiB L1 下預期 32 misses、100% 使用比例。16 KiB L1 下 AoS 可以留住全工作集，但仍會取得較多 cold bytes。若三次 capture 不一致或 checksum 不同，停止比較並保存失敗資料。

此案例不保證 SoA 永遠優於 AoS。下一步可用「所有欄位都需要」的反例確認取捨；GEMM tiling、L1I hot/cold function、逐 task／PSF 時間同步仍是後續工作。
