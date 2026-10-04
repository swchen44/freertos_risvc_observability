# T2d：小延遲會流失，改用累加成本後通過驗證

**數十 ns 的累計成本已能可靠加入 guest virtual time。** 原本 `mtime anchor + delay` 的絕對目標方式會流失延遲；新增研究用的相對成本 API 後，10／20／50／100／1,000 ns 各 1,000 次的累計增量全部符合預期。單次請求與一次排入 10 筆成本都測過，各三次結果一致。

這仍是 **async callback 生效時累加時間**，尚未代表 memory instruction 當下立即 stall，也未接上 cache 模型或產品 CPU 頻率。

## 同一 QEMU binary 的三組對照

正式三組全部使用套用 patch 0001～0003 的相同 binary、相同 firmware。每組 control／啟用各三次，18 次 QEMU 執行；每次有五種延遲、每種 1,000 次請求。Scheduler 尚未啟動，沒有 tick ISR 干擾；相對 control 核對每個測量窗口的 guest 指令數完全相同。

| 每筆成本 | 預期累計增量 | 絕對目標實際增量 | 保留比例 | 累加成本增量 | 拆成 10 筆累加 |
|---:|---:|---:|---:|---:|---:|
| 10 ns | 10,000 ns | 0 ns | 0% | 10,000 ns | 10,000 ns |
| 20 ns | 20,000 ns | 300 ns | 1.5% | 20,000 ns | 20,000 ns |
| 50 ns | 50,000 ns | 14,000 ns | 28% | 50,000 ns | 50,000 ns |
| 100 ns | 100,000 ns | 64,000 ns | 64% | 100,000 ns | 100,000 ns |
| 1,000 ns | 1,000,000 ns | 964,000 ns | 96.4% | 1,000,000 ns | 1,000,000 ns |

正式證據：[absolute v2](../runs/clock-nano-absolute-v2/results.json)、[relative v2](../runs/clock-nano-relative-v2/results.json)、[burst v2](../runs/clock-nano-burst-v2/results.json)。`v1` 保留作探索紀錄，正式比較引用 `v2`。

每個正規測量窗口只有 1,000 筆邏輯請求。Burst 模式將每筆成本拆成十份，在同一個 instruction callback 內連續呼叫相對 API 十次；例如 10 ns 拆為十筆 1 ns。`api_calls` 保存真正呼叫次數：control 為 0，single 為 1,000，burst 為 10,000。一次排入多筆後，處理時逐筆累加，沒有被後續目標覆蓋。

## 為什麼絕對目標會失真

Guest `mtime` 的 10 MHz 解析度為 100 ns；取樣到函式入口、再到 async callback 生效，需要額外指令與 TB 邊界處理。當目標 `sample + 10 ns` 已落後現在時間，單調 clock 不會倒退，該筆請求便沒有增加成本。

較大的 delay 也受到取樣與生效間隔影響，例如 1,000 ns 並未完整保留。這不是 cache miss 模型本身的問題，而是把額外成本當作舊的絕對時間目標。

## 新增的 POC API

[第三項 patch](../tools/qemu/0003-experimental-relative-clock-cost.patch) 提供：

```c
void qemu_plugin_poc_add_ns(const void *handle, uint64_t delta_ns);
```

**這是本研究自行新增的 API，不屬於官方 QEMU。** 必須使用相符的 patched binary，宣告在 [poc-clock-api.h](../tools/qemu/poc-clock-api.h)。既有官方 `qemu_plugin_update_ns` 保留，讓失敗對照與過期目標測試可重跑。

處理方式：收到 delta 後排入 CPU async work；執行 callback 時重新讀 QEMU virtual clock，以 `now + delta` 推進。加入 signed-ns 溢位與 vCPU context 檢查。沿用前兩項 patch 的 single-vCPU／fixed-icount setter 和無 timer fallback；本輪只驗證 64-bit host、RV32 guest。

```mermaid
flowchart LR
 A[記錄本次成本 delta] --> B[排入 async work]
 B --> C[callback 執行時讀 now]
 C --> D[檢查 now + delta 範圍]
 D --> E[推進 virtual clock]
 E --> F[下一筆 callback 重新讀 now]
 F --> G[累加下一筆成本]
```

## 驗收如何避免假通過

- 對照相同 firmware、相同窗口指令數、無 tick 干擾。
- 每種成本必須真的經過 1,000 次 marker，plugin 核對 id／delay／窗口順序。
- 以 guest mtime 實測區間減去 control 區間，再比較 `delay × 1000`。
- `mtime` 每 100 ns 才能辨識，四個端點差分容許 200 ns；不宣稱直接量到單筆 1 ns 的完成時間。
- PSF `NANO_BEGIN`／`NANO_END` 必須包住 guest 測量，且具有 `COMPLETE`。
- `captures_valid=true` 只表示資料完整；`all_delays_reliable` 才表示五種延遲全部符合累計預期。絕對模式前者為 true、後者為 false。

[比較器](../src/psf_lab/nano_clock.py)、[7 個正常與反例測試](../tests/unit/test_nano_clock.py)。反例包括請求完整卻完全未生效、部分流失、指令數改變、timer 干擾與時間倒退。

## IRQ／WFI 回歸

另外使用相對 API 重跑 T2c，control／啟用各三次，六次全部通過：[結果](../runs/clock-edges-relative-v1/results.json)。沒有 timer、連續成本、IRQ 遮蔽／恢復、WFI 後重新注入均有 guest 證據。過期目標仍用原本 absolute API 測試，確保相容行為。

Receipt 以 `mode=relative_cost`、`target_ns=null` 表示沒有向 API 傳送絕對目標；`anchor_target_ns` 只作比較參考，不能誤當成實際 API 請求。新增一個 unit test 驗證這個區別。

## 重建與使用

[重建腳本](../tools/qemu/build-clock-probe.sh) 現在會產出 baseline／setter／clock／relative 四個 binary。新增 patch 需要 Meson 重新產生建置檔，腳本已 export 獨立 venv 的 `NINJA`，避免重新偵測時找不到。初次失敗與修正後 build log 均保存於 [驗證目錄](../artifacts/verification/clock-nano/)。包裝腳本經語法檢查；其 configure／build／patch 命令已實際執行，沒有宣稱本輪重新從空目錄完整執行 wrapper。

```sh
./tools/qemu/build-clock-probe.sh .tools/qemu-relative-rebuild

# 相對成本；output 目錄須不存在
PYTHONPATH=src .venv/bin/python tools/tcp/run_clock_nano.py \
  --relative --qemu .tools/qemu-relative-rebuild/qemu-system-riscv32-relative \
  --output runs/local/nano-relative

# 同一 callback 一次排入十筆成本
PYTHONPATH=src .venv/bin/python tools/tcp/run_clock_nano.py \
  --relative --burst \
  --qemu .tools/qemu-relative-rebuild/qemu-system-riscv32-relative \
  --output runs/local/nano-burst

# IRQ／WFI 回歸
PYTHONPATH=src .venv/bin/python tools/tcp/run_clock_edges.py \
  --relative --qemu .tools/qemu-relative-rebuild/qemu-system-riscv32-relative \
  --output runs/local/edges-relative
```

移除 `--relative` 即重現絕對模式流失。`--burst` 只允許搭配 `--relative`。CLI exit 0 表示研究矩陣跑完，不等於各延遲通過。

Firmware 位於 `firmware/app/cases/clock_nano.c`，plugin 位於 `tools/tcp/clock_nano.c`；資料及每次命令／來源／ELF／PSF／plugin binary hashes 在 `runs/clock-nano-*-v2/`。

## 接回 sysram 10 cycles 前的決策與邊界

10 cycles 在 100／500／1,000 MHz 分別是 100／20／10 ns。這三種 ns 成本的累計注入均已通過，但**產品 CPU 頻率尚未確認**。這些換算不代表目前 `-icount shift=0` 已模擬相應 CPU pipeline。

下一步需要選定換算頻率或研究情境矩陣，再接 `CycleBudget` 與 L1／L2／sysram 成本。必須明訂 icount 原有 instruction time 和新增 memory service 是否重複計入、以何種方式分開報表。

仍未完成：

- 每次 memory callback 的模型計算、跨 line／region、read／write policy 接合。
- 實際 guest instruction 尚未完成時的 stall／IRQ 相對順序。現在只證明 async 邊界累計成本守恆。
- 每筆額外 async work 的 host CPU／記憶體代價與大 trace 吞吐；不能把本輪成本比例當作 SDK CPU loading。
- 真實 TCP A/B 再擷取 PSF；Web／離線 timing dashboard。
- SMP、adaptive icount、record/replay、migration 及產品硬體校準。

提交後完整回歸 **182／182 通過**，Ruff 與本輪 Python 格式檢查通過。[完成紀錄](../artifacts/verification/clock-nano/completion.json)、[完整 log](../artifacts/verification/clock-nano/full-tests.log)、[三種模式／patch／hash 核對](../artifacts/verification/clock-nano/receipt.json)。CPU 頻率或情境矩陣待使用者選定；尚未開始依賴該選擇的 cache 接合。
