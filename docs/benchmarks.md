# 容量與效能量測

這裡量的是本機 parser／Dashboard 容量。合成輸入為固定五個 task、每 100 ticks 切換，不能代表 recorder event mix，也不能推估板端 SDK CPU loading、UART bandwidth 或 cache penalty。

## Parser

Python 3.13.2、Apple Silicon macOS 15.7.7。每組以新 subprocess 量測，生成 fixture 不算入解析時間；warmup 1 次、正式 5 次，p95 使用 nearest rank，5 次樣本的 p95 等於最大值。所有原始時間、環境、SHA-256 與 fixture 見 [parser.json](../artifacts/benchmarks/parser.json)。

| Events | Bytes | Median ms | p95 ms | Peak RSS MiB | tracemalloc peak MiB |
|---:|---:|---:|---:|---:|---:|
| 1,000 | 12,072 | 2.32 | 3.23 | 19.55 | 1.01 |
| 10,000 | 120,072 | 33.34 | 36.46 | 29.62 | 10.30 |
| 100,000 | 1,200,072 | 1181.54 | 2094.28 | 128.97 | 103.26 |

RSS 是該 subprocess 在 warmup／timed parse 後的 high-water，含 Python runtime 與輸入，讀取時點在 tracemalloc 前；macOS `ru_maxrss` 原單位為 bytes，Linux 為 KiB。tracemalloc 另跑一次解析，只計 Python 追蹤到的配置，不能當成整個程序 RSS。測試期間 host 有其他工作，這組數字是觀察值，不能當硬體保證或服務 SLO。

## 瀏覽器

Chromium 153.0.8010.12、viewport 1600×1000。本表每個規模一次觀察，尚未做分布或跨機統計。從真正 PSF 上傳開始，最後由 `psf-settled` render event 確認完成，沒有以固定 sleep 推算。API 解析、JSON 查詢與 ECharts／Tabulator 都走實作。

| Events | 上傳至首圖 ms | Query 至 render ms | Filter 至 settled ms | Timeline SVG elements | 表格本頁 |
|---:|---:|---:|---:|---:|---:|
| 1,000 | 194 | 145.8 | 42.0 | 1037 | 20 |
| 10,000 | 423 | 285.0 | 193.4 | 2038 | 20 |
| 100,000 | 5038 | 2792.8 | 1448.0 | 2038 | 20 |

原始記錄：[capacity.json](../artifacts/browser/capacity.json)、[11 組瀏覽器測試](../artifacts/browser/results.json)。10k／100k timeline 以 `density_by_interval_start` 聚合，至多 2,000 marks；SVG elements 還含座標軸、文字與 slider，因此不是 mark count。密度圖表示區間起點的數量，不表示精確佔用時間；task share 仍由完整 intervals 計算。

本次 100k 首次載入約 5.0 秒、篩選約 1.4 秒，目前不適合即時高速連續更新。後續若需要更快，應先量 JSON 載入、查詢與 40-bin trend 成本，再考慮索引、共用載入 cache、預先聚合與 worker；不可先降低原始資料保真度。產品可接受延遲尚未指定，測試的 10 秒一般等待／30 秒大型載入／60 秒情境上限只是 hang guard。

重跑命令：

```sh
.venv/bin/python -m psf_lab benchmark --events 1000 10000 100000
npm --prefix web run build
npm --prefix web run test:e2e
```

所有效能量測與 memory 上限應隨版本重新記錄；此處沒有宣稱 200k events 是已量得的最佳容量。

前一輪同機 100k 首次載入約 10.3 秒，本次完整數字如表；host 負載會影響結果，不以單次變快宣稱修正提高效能。
