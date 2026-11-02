# 儲存空間盤點與清理範圍

日期：2026-11-03。**第二次清理完成，Task7開發維持暫停。** [最新清理與還原收據](../artifacts/verification/storage/cleanup-paused-20261103/README.md)：四份已封存的重複capture／runtime目錄已移除；兩份失敗QEMU source先完整封存、實際還原並逐檔核對後移除。觀測可用空間增加約1.76GiB，清理結束約4.0GiB；現用工具與唯一證據保留。source備份分成每份最多64MiB，附還原指令與SHA清單。

Tasks1–6已完成及發布；Task7只有RED測試草稿，已保存接手點；正式16-run仍未執行。以下是**第一次清理的歷史盤點**，當時完成Tasks1–4；[第一次執行收據](../artifacts/verification/storage/cleanup-20261103-r2/README.md)保存先前約563MiB的清理證據。

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

第一次清理後續作Tasks5–6。最新使用者要求暫停Task7，第二次清理結果見頁首；等待恢復指示再續作。完整C2b內網還原包仍屬Task8，本頁兩次清理備份不代表整個pilot還原交付完成。

本次清理備份已保存於本機 Git；上傳在600秒後逾時，遠端仍停在Tasks1–6 checkpoint。完整狀態與重試接手點見[清理收據](../artifacts/verification/storage/cleanup-paused-20261103/README.md)。開發維持暫停。
