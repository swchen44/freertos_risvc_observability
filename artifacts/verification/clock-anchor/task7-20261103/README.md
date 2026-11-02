# C2b Task7：對照分析與報告

來源 `aba298d4`，2026-11-03。相關18個測試通過，完整suite396個：391通過、5個opt-in skip。Ruff check及本輪五個Python檔format通過；全庫十個baseline format舊問題仍未改動。

L/C、C/O核對完整packet／oracle／資源／raw costs／PSF bytes／guest計時。O/M另核對應用結果，保留負差值，以M為分母計算六位小數百分比，分母0為null。host wall／child CPU只列原始配對，不宣稱穩定產品overhead。

JSON／CSV／Markdown報告有架構與時序Mermaid；CSV採UTF8、QUOTE_ALL、CRLF，formula文字防護與signed numeric欄位分開。報告fixture核對16個identity及20筆O anchor輸出，這是格式／流程測試，不是真QEMU正式16-run。

新增RED反例證明並修正：full須先重新驗證四份smoke、smoke須檢O/M應用一致性、O/M不能只比packet而忽略oracle outcome、verified-bounds須有五個anchors。先前沒有執行過正式captures，因此沒有用放寬條件重採樣。

`code-size.tar.gz`含真size -A、symbols、readelf、反組譯、map與比較JSON。兩個candidate新`.text`為39782 bytes，固定歷史參考39014 bytes，整個build差768 bytes；包括helper／init／layout，不能稱為SDK本身大小。code-size CLI命令與來源SHA一併保存。

本輪正式16-run仍為0。Task8負責真smoke／full、完整還原、獨立whole-change review與發布；Web／offline Dashboard未變更，不計UI驗收。
