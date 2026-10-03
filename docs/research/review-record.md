# 下一階段研究 review 紀錄

日期：2026-10-03。審查範圍是研究文件與驗收提案，沒有新 firmware、正式 decoder 或 Dashboard 可判定實作通過。

## 1. 分工與方法

- PSF 研究：讀本地兩套 recorder、XML、實際 PSF 與開源 parser；保留一次性唯讀探測方法。
- 模擬研究：讀官方 FreeRTOS demo、固定 Kernel、QEMU、工具鏈文件與本機工具狀態。
- 設計研究：使用 `frontend-design`／`web-design-engineer`，閱讀官方 UI／功能及本地八張原圖；提出套件與互動取捨。
- 獨立 reviewer：使用 `requesting-code-review` 的唯讀方法，取得明確需求與檔案範圍，核對文件、SDK source、部分官方文件，實際執行 PSF 文件中的 probe。
- 主代理：另行以 `struct` 讀取現有 PSF 的 header 與事件邊界，確認 7,152 bytes、309 events、word width 8、1 MHz、event offset 152、序號 5～313、沒有相鄰 sequence gap。

## 2. Review findings 與處理

| 嚴重度 | 發現 | 處理 |
|---|---|---|
| Critical | 未發現 | 結論限於已查的研究範圍 |
| Important | 模擬文件將 native／container、capture 等工程項目列為使用者必決，UI 文件也要求先確認手勢／快捷鍵 | 已改成 agent 提案與驗證；只有會改變交付、成本、資料支援範圍或使用目的時才釐清 |
| Minor | QEMU v8.2.2 ACLINT timebase 的引用行號應為 72，原寫 78 | 已修正官方來源連結及文字 |
| Minor／建議 | 直接寫出兩種 kernel schema key，減少讀者追 source 的負擔 | 已補桌面 `0x1FF1 / my_krnl / 1.0.0`、主 FreeRTOS `0x1AA1 / FreeRTOS / 1.2.0`；主代理再查本地 header 定義 |

主代理另調整 Dashboard 資料流圖：PDF 文件的章節／圖表篩選與 PSF 的事件／時間篩選分開，透過案例來源連結關聯。圖表不將 PDF 證據混成 scheduler events。

## 3. reviewer 刻意未下結論的部分

| 項目 | 缺少的證據／原因 |
|---|---|
| QEMU＋工具鏈＋FreeRTOS＋SDK 的實際相容性 | 尚未安裝、build 與執行這個組合 |
| 正式 decoder 的容錯與分析正確性 | 目前只有限定既有檔案的研究 probe |
| `unittest`／Ruff／browser 測試是否通過 | 尚無新專案與測試產物 |
| UI 操作、效能與可用性 | 尚未做 prototype、資料規模及效能驗收 |
| 與商用 Tracealyzer 的結果一致性 | 未執行商用 viewer；遵守不購買的要求 |
| 每張原圖與每個第三方功能 | 獨立 reviewer 只抽核官方功能頁與部分表格文件；設計研究另記錄逐圖閱讀及來源 |

## 4. 驗收範圍

研究 review 可以幫助修正事實、缺口與決策負擔，不能取代後續實作驗收。新 Python 專案仍需要 `unittest`、`ruff check`、`ruff format --check`；模擬要保存 PSF／獨立 oracle／JSON，HTML 要實際操作與比對 CSV。

文件／PSF／Mermaid 的檢查另見 [本階段驗證結果](verification.json)。該結果不表示新產品測試已執行。
