# C2b Task 6：獨立因果驗證與 PSF join

2026-11-03，最新來源 `5ed35acb`。相關 35 個單元測試通過；完整 suite 385 個：380 通過、5 個 opt-in skip。明確啟用的 runtime retry2 為 3／3 通過、0 skip；其後修正完整 uint64 wrap 與品質狀態，再執行正向 O capture 與 guest mode／cmdline 共 3 個測試，3／3 通過、0 skip。

實際 baseline O 的 431,823 筆 access 以鎖定的 L1I8KiB／L1D8KiB／L232KiB profile 獨立 replay；431,823 組 request／applied、78 組 MMIO 與五組 SDK marker 完整核對。取得 5 組 verified-bounds，431,512 rows 介於觀測之間，311 rows 維持 unknown。這不是逐筆 timestamp，也沒有新的解析度門檻；resolution 仍為 unrated。

## 反例與修正

- wrong ABI／SMP／icount／unsafe context／缺 MMIO 成功 callback：實際 QEMU 拒絕；ABI CLI 另包含 10 個 subcases。
- 缺 footer、重複 request、hash mismatch：串流改寫副本驗證，原始資料保留。
- duplicate／跳號／錯 delta／錯 row／apply reorder／target／cursor／pending／footer：手工 protocol fixtures 核對指定 error code。
- TS32／EventCount16 wrap、完整 MTIME64 wrap、uint64 offset wrap、same tick、錯 payload／phase、候選缺失／不唯一及 unknown PSF：單元測試。
- IRQ 位於 enter→sampled 或 sampled→leave：保留兩段 context，不宣稱 SDK exclusive CPU。
- plain／gzip 得到相同 causal summary；兩次 scan 核對實際消費內容 SHA。generator＋tracemalloc 驗證已消費 rows 不累積於 reader 記憶體。

首次 runtime harness 把 unittest 的 `run()` 覆蓋成 Path，修正命名；實際 wrapper 又抓到重複 raw_rows keyword。uint64 wrap 的 RED 測試證明直接比較 counter 大小錯誤，改用 native 時間與 modular 差值。完整失敗／修正 logs 均保留。

## 檔案與邊界

`runtime-archives.json` 對照各次 runtime archive 與原始目錄。各 tar.gz 包含完整 capture、成功 validation、故意破壞的副本、ABI 命令與拒絕結果；`inventory.json` 保存 archive／log SHA256，每檔小於 64MiB。`progress-ledger.md` 保存實作決策。

Task6 完成獨立 validator；正式 16-run 仍未執行。L/C、C/O 透明性、O/M 成本、完整來源還原與最終獨立 review 仍在 Task7／8。Web／offline Dashboard 尚未接合本輪資料。
