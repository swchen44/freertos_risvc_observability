# Parser 支援範圍

CLI：`python -m psf_lab decode fixtures/desktop/trace.psf --output artifacts/local/desktop-trace.json`。

已實作little-endian streaming PSF v14，desktop64-bit `0x1FF1/my_krnl/1.0.0`與RV32 `0x1AA1/FreeRTOS/1.2.0`分開派送。真實desktop固定檔驗證309 events、50 cycles、Counter 0～49；RV32目前先用獨立手工binary測試，新firmware執行另記證據。

`src/psf_lab/parser/schemas/desktop.py`事件來源為baseline桌面trcKernelPort.h 134～193行及XML；FreeRTOS來源為主SDK trcKernelPort.h 523～647行。支援task生命週期／switch、queue／semaphore／mutex事件、priority、name、inline/fixed user events；schema模組列明ID。未納入的事件保留payload並標unknown，不宣稱全部SDK功能皆可解讀。

- Strings到NUL停止，保留原始padding；printf只解讀`%d/%u/%x/%%`，其他保持literal與參數並顯示限制。
- Timer第一版解讀free-running32-bit increment；採事件間小於一次wrap的前提，超過半個counter範圍的推導標不確定。其他timer保留raw timestamp，不輸出假時間。
- Gap／unknown事件使當前actor失去可信度，直到已知task switch。ISR執行時間尚未重建，不能聲稱完整CPU utilization。
- 物件以address＋epoch區分重用；raw64-bit數值以字串保存。只有name並不代表已看見create。
- Strict拒絕截斷；`--partial`只保留完整event prefix。Header／metadata損壞仍拒絕。Restart／多session、SMP、multistream、ring RAM dump與其他version拒絕。
- 無gap不保證收集完整，`capture_complete`保持null，直到harness核對completion與獨立oracle。

限制：PSF無每事件checksum，不能保證識別所有bit flip。頻率需外部校正；parser不把來源宣告值當實體頻率證明。

## 已實作的排程分析

`analyze` 以明確 task switch 建立 running intervals；首個 switch 前、sequence gap 相鄰區間、未知事件與 ISR 未重建區間列 unknown。COMPLETE 才關閉 capture 尾端，否則保留 open interval。Task share 的分母包含 unknown 時間；它不是包含 ISR 的整體 CPU utilization。Request response 與 worker execution 分開，缺完成或執行證據時為 null。物件 epoch 分開計算。

FreeRTOS notification family 0xC9～0xCD 已解碼為 task target／wait 事件，來源 `trcKernelPort.h:687–691,1471–1538`；actor 與通知對象分開。FreeRTOS `TRACE_HANDLE_NO_TASK=2` 為 reserved startup sentinel，不建立 task。
