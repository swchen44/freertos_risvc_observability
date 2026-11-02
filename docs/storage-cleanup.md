# 儲存空間盤點與清理範圍

日期：2026-11-03。**使用者已確認保守清理，執行完成。** [執行收據](../artifacts/verification/storage/cleanup-20261103-r2/README.md)保存重新驗證、移除清單與重編metadata；下方候選表保留清理前盤點。 C2b已完成Tasks1–4；Task5 brief已讀，尚未新增Task5程式碼。

## 占用

`du`顯示：`artifacts/`約2.8GiB、`runs/`約2.0GiB、`.tools/`約5.9GiB。其中`artifacts/local/`約1.4GiB，`runs/local/`約465MiB。這些是目錄配置量；實際可回收量須清理後再量測。

| 項目 | 大小 | 建議與證據 |
|---|---:|---|
| 已封存的四組重複runs／還原副本 | 約90MiB | 已逐檔對照tar：946個檔案全相同，無額外／缺少檔；可由已push archive還原 |
| `artifacts/local/github-clone-verification/` | 約258MiB | root與POC皆無修改／untracked檔；46個ignored檔僅Python bytecode。為舊驗證clone，可重新clone現有repo |
| 兩個失敗QEMU build與舊reference build的`.o/.a/.fa` | 約204MiB | 可重編的cache；保留source、logs、manifest、binary與目前接受的r3 build。重編不承諾bit-identical物件檔 |
| `artifacts/local/`其餘歷史trial／before-fix資料 | 約1.1GiB | 先查是否已封存；不能因名稱含local就當成不需要 |
| 正式tracked artifacts／runs | 邏輯bytes約1.49GB／0.93GB | 部分仍供Dashboard、分析與測試使用，保留 |

四組archive核對的確切路徑、檔案數、bytes及clone／cache盤點在[原始audit](../artifacts/verification/storage/20261103/audit.json)。此頁的約90MiB為94,133,469 bytes；cache為214,048,184 bytes。

## 保守清理候選

- `runs/local/c2b-guest-probe-restored-20261102/`：已完成還原核對的副本；保留實際使用的`c2b-guest-probe-20261102`。
- `runs/local/c2b-clock-regressions-20261103/`：對應Task4的`clock-regressions.tar.gz`。
- `runs/local/c2b-abi-20261102-r1/`：對應Task4的`abi-failed.tar.gz`。
- `runs/local/c2b-abi-20261103/`：對應Task4的`abi-accepted.tar.gz`。
- 舊驗證clone與前表列出的可重建物件cache。

舊驗證clone的root commit已不在現行main ancestry，且含先前要求移除的`percepio-observability-research.zip`。它的舊Git歷史不會重新打包上傳；POC commit仍為現行POC ancestor。移除這份一次性clone不代表重寫目前repo歷史。

保守清理已執行：946個已備份副本、一次性舊clone及3305個可重建物件檔已移除。觀測可用空間增加563.32MiB；logical移除量為573379682bytes。沒有刪唯一trace、tracked檔或目前使用中的工具。

## 擴大清理

若使用者選擇擴大範圍，再封存`artifacts/local`歷史trial及失敗QEMU工作目錄。每個目錄先產生inventory、保存來源／patch／build命令，再實際還原核對；沒有完整備份的資料先保留。不得用`git clean -fdx`或整批刪掉`runs/`、`artifacts/`、`.tools/`。

清理後記錄刪除清單、可還原來源、實際回收量及Git狀態，再續作C2b Task5。完整內網還原包仍屬Task8，這份audit不代表已完成還原交付。
