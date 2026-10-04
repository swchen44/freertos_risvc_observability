# Z0：固定 request／response 的 zero-copy TCP 基準

2026-10-04。使用者選擇 A：小型 request、較大 response。本輪完成新案例與分析，**尚未套用新的最佳化，也尚未實作 cache latency／guest stall**。

## 工作負載與已驗證結果

- 單一 FreeRTOS task，lwIP 2.2.1 raw API、`NO_SYS=1`，checksum algorithm 3。
- 一次握手，兩輪 64-byte request；每輪回傳四個 1,460-byte segment，共 11,680 bytes response。
- TX 使用 `tcp_write(..., 0)`。同一個 payload buffer 僅在前一段資料完整 ACK、`retained_bytes == 0` 後覆寫。
- 每輪執行一次 `tcp_fasttmr()`／`tcp_slowtmr()`，這是受控呼叫成本，沒有真實等待。
- Peer 主動 FIN，server 被動關閉，收到最後 ACK，再關閉 listener。
- 每次保存 **25 個雙向 IPv4/TCP 封包**，Python 獨立檢查 IP／TCP checksum、payload、seq／ACK、方向、位址與完整結束。
- 三次 QEMU 重跑的分析結果完全一致。收送 bytes、buffer ownership、PCB／pbuf 與 lwIP heap 清理皆通過。

正常完整 ACK 案例已通過；partial ACK、error／abort、重傳與多個 in-flight buffer 的 ownership 擴充仍未驗證。這一版刻意一次只保留一個 1,460-byte TX buffer，不代表 TCP window 已最佳化，也不代表完整 NIC zero-copy。

## 如何量測，如何避免誤判？

一份連續 I/D trace 覆蓋 listener 建立至關閉及資源檢查。**連續 cache trace 包含同一 guest 內的測試 peer、request／payload 產生、封包 RAM 快照與驗證**；檔案輸出在 capture 後才執行。因此可重現模型的連續狀態，但不能把這份 cache 統計當成純 TCP stack footprint。

另用 `z0_stack_begin/end` 標記協定／應用回呼區段，排除 peer 建包、封包快照與傳送後的 payload 比對。`rdinstret` 與 trace marker 的邊界不同，前者總計 **54,200**，後者 **54,362**；差額為 27 個 window 各 6 條邊界指令。函式 self instructions 的分母採後者，階段占比採前者。

這些區段仍包含正確性 assertions、callback 的 request 內容檢查與 lwIP stats 計數。不是無 instrumentation 的產品成本。Capture 全程關閉 IRQ，以維持 bounded deterministic 實驗；不能據此分析正常 FreeRTOS 搶佔、真實 RTT 或 CPU task usage。

### 協定階段

| 階段 | 兩輪合計指令 | 占所有量測區段 |
|---|---:|---:|
| Response TX | 27,804 | 51.30% |
| Response ACK | 10,726 | 19.79% |
| Request RX | 5,954 | 10.99% |
| SYN 處理 | 2,757 | 5.09% |
| Peer FIN | 1,820 | 3.36% |
| 建立連線最後 ACK | 1,332 | 2.46% |
| 關閉最後 ACK | 1,320 | 2.44% |
| Server close | 1,091 | 2.01% |
| Listener 建立 | 912 | 1.68% |
| Idle timer 呼叫 | 374 | 0.69% |
| Listener 關閉 | 110 | 0.20% |

### 協定／回呼區段函式熱點

| 函式 | Self instructions |
|---|---:|
| `lwip_standard_chksum` | 20,508 |
| `tcp_input` | 3,817 |
| `tcp_output` | 3,005 |
| `inet_chksum_pseudo` | 1,945 |
| `ip4_input` | 1,806 |
| `tcp_receive` | 1,641 |

`lwip_standard_chksum` 占區段 trace 約 **37.72%**。下一個值得研究的是其實際掃描／對齊路徑及 packet／pbuf 組成，再選擇單因素比較，不能預先宣稱還能改善多少。改變寫入批次或 in-flight bytes 也可能降低每 byte 的協定處理成本，但會改變封包數、RAM 與等待行為，須另列實驗。

若直接看全 session 函式表，`memcmp`／`memcpy` 仍很大，主要包含測試工具的封包保存與驗證。**不能據此聲稱 zero-copy 失效，也不能把最佳化 oracle 當成 TCP 最佳化。** 分析 JSON 同時保留兩張熱點表。

### Cache 與 footprint

| 項目 | 數值／邊界 |
|---|---|
| L1I／L1D／L2 | 16 KiB／16 KiB／64 KiB，64-byte line、4-way、LRU |
| L1I／L1D／L2 miss | 280／309／560，包含 harness 的整段連續 replay |
| Trace I／R／W 操作 | 301,764／48,725／31,952 |
| 整份 ELF text／data／bss | 40,164／144／296,672 bytes，含 FreeRTOS、SDK、TCP、封包快照與測試程式 |
| Peak retained TX payload | 1,460 bytes；不是 TCP stack 全部 RAM 使用量 |
| 結束資源 | lwIP heap 使用量、TCP PCB、listener PCB、TCP segment、pbuf header、pbuf pool 都回到起始值 0 |
| 未模擬 | cycles、dirty writeback、bus arbitration、DMA、prefetch、pipeline |

與先前 TX-only cold-per-phase 的數字有不同觀測邊界，也開啟 `LWIP_STATS`，不能直接相減當成最佳化收益。

## 重跑與證據位置

```sh
# 在 poc/，output 必須尚不存在
.venv/bin/python tools/tcp/run_session.py --output runs/local/z0-new
# 可加 --toolchain /path/to/bin --qemu /path/to/qemu-system-riscv32
```

需沿用專案 Python 環境、RISC-V GCC、支援 API 7 的 QEMU、host C compiler、GLib headers／pkg-config。此命令驗證 pinned lwIP source hashes，建立獨立 firmware，執行三次並檢查 repeatability；不需要改原本 transfer dataset。

| 位置 | 用途 |
|---|---|
| [tcp_request_response.c](../firmware/app/cases/tcp_request_response.c) | 新 firmware，協定流程、buffer ownership、capture 與資源 assertions |
| [run_session.py](../tools/tcp/run_session.py) | 建置、QEMU、封包／PSF／trace 驗證及報告 |
| [tcp_session.py](../src/psf_lab/tcp_session.py) | 獨立固定 workload oracle |
| [test_tcp_session.py](../tests/unit/test_tcp_session.py) | 正常、錯誤 payload、非法 ACK、漏 final ACK、資源洩漏與額外封包測試 |
| [v2 manifest](../runs/tcp-session-z0-v2/manifest.json) | 正式基準 source／tool hashes、命令及三次 run receipts |
| [第一輪分析](../runs/tcp-session-z0-v2/z0-1/analysis.json) | 階段統計、兩種函式熱點、cache 模型與資源紀錄 |
| [第一輪 PSF](../runs/tcp-session-z0-v2/z0-1/trace.psf) | Session 開始／結束標記；細部 instruction window 在 trace＋sidecar |
| [驗證紀錄](../artifacts/verification/tcp-session-z0/) | Python／Ruff／完整性驗證的原始結果 |

`runs/tcp-session-z0-v1` 是加入 stack window markers 前的探索版；正式引用以 **v2** 為準。兩者皆保留，沒有覆寫先前三配置的成果。

## 驗證結果與未完成項目

- 全部 133 個 unit tests 通過，包含新增的 6 個 oracle tests；三次實際 QEMU session 通過。
- 全套 `unittest discover -s tests`：139 個，136 個通過、3 個 error。`test_real_priority_pair`、`test_real_controlled_pair`、`test_formal_clean_queue_run` 被既有 `Formal run requires committed, clean sources` 檢查擋下，未進入對應 QEMU 測試。初次執行時尚未 commit，沒有繞過檢查。
- 更新：依使用者要求 commit 後，乾淨來源重跑 **139／139 通過**，包括上述三個整合測試。證據為 [committed-full-tests.log](../artifacts/verification/tcp-session-z0/committed-full-tests.log)。Z0 commit `a5d2f22` 已 push，主倉庫 `d238be4` 已更新 submodule 指標。
- `ruff check .` 通過；新增三個 Python 檔的 `ruff format --check` 通過。全庫 format check 指出 10 個既有檔案需格式化，本次未改寫那些檔案。
- 尚未新增 Z0 的 Web／離線視圖；既有 TCP Dashboard 仍只顯示原本三配置。尚未執行新的 UI E2E。
- 尚未完成 Z1～Z4、partial ACK／abort 清理、T2 guest timing 或新的 A/B 最佳化。

新的記憶體速度要求見 [QEMU 分層記憶體延遲研究](research/QEMU分層記憶體延遲研究.md)。[T1 成本估算已完成](memory-timing-t1.md)，真正改變 guest virtual time 的 T2 仍待驗證。
