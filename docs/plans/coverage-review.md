# 實作計畫覆蓋與自我檢查

日期：2026-10-03。依 writing-plans 的 Self-Review 對照設計、檔案責任、介面、測試及失敗模式。**這是計畫文件檢查，產品尚未實作，沒有宣稱 unittest／Ruff／模擬／瀏覽器已通過。**

## 設計到任務

| 設計要求 | 主要負責任務 | 驗收證據 |
|---|---|---|
| 指定 POC 路徑、Git、版本與來源 | P1-T1、T5 | source lock、clean check、run manifest |
| RISC-V／FreeRTOS 真實執行 | P1-T1、T4 | 原始demo smoke、ELF／map、QEMU log |
| SDK hooks／是否改 kernel | P1-T4 | config、重編、預處理檔、實際RTOS events |
| 時間校正 | P1-T4 | DTB timebase、mtime／tick、PSF換算 |
| Capture完整性／semihosting | P1-T4、T5 | partial-write／error tests、completion、close、oracle |
| Desktop與RV32兩種PSF | P1-T2、T3 | 真實fixture＋手工binary＋新RV32 PSF |
| Unsupported／truncation／unknown | P1-T2、T3 | strict／partial／明確錯誤／raw保留 |
| JSON精度／lifecycle／wrap | P1-T3 | 64-bit、epoch、NUL、wrap／gap測試 |
| 獨立oracle／case expectations | P1-T5 | IDs／counts／completion與PSF互相比對 |
| Interval／request／品質 | P2-T1 | 手算排程、缺漏／open窗口與原始offset |
| Logger兩配置 | P2-T2 | 相同工作量與request pair assertions |
| Inversion／inheritance | P2-T3 | 控制順序、鎖類型、priority／排程證據 |
| Deadlock／ordered locks | P2-T4 | 等待環、supervisor、修正後完成 |
| 重複實驗與案例教學 | P2-T4 | 21個run、三組pair與問題→修正→重測 |
| Filters與全部CSV | P3-T1 | 250筆／page20測試、query／CSV集合與排序一致 |
| 本機服務／可重啟保存 | P3-T2 | TestClient、真實API、上限／path／restart |
| SVG／互動時間軸 | P3-T3、T4 | 真實SVG DOM、brush／zoom／pan／hover |
| 表格sort／resize／move | P3-T3、T4 | API sort、實際拖動及DOM結果 |
| Raw／品質／詳細資訊 | P3-T3、T4 | offset、unknown、空／partial資料顯示 |
| Case比較 | P3-T2、T3、T4 | verified run registry、request-relative對齊 |
| 大資料效能 | P3-T4 | 1k／10k／100k、5次原始值與SVG預算 |
| 本地資產／未來離線邊界 | P3-T3、T4 | 本地bundle、license、無CDN、DataSource |
| unittest／Ruff／browser | 各任務、P3-T4 | 實際exit／log，沒有以skip當通過 |
| 報告／README／內網交接 | 各里程碑、P3-T4 | evidence矩陣、操作圖、未完成U任務 |

## 本輪已修正的計畫一致性

1. Task與object filter分開：event新增actor_id，filters新增task_ids；queue目標handle不能當成執行task。
2. 時間語意統一：event ticks相對trace origin，UI先減window origin再轉Number；保留raw timestamp。
3. Priority案例確認H已blocked才放行M／L；固定等待不是狀態證據。
4. Ordered-lock案例不用ABBA的持鎖barrier，避免控制程式自己造成修正版deadlock。
5. 單獨run要求clean；suite只容許自身新建產物，所有來源保持同一commit／hash。禁止透過suite規則放行dirty source。
6. 原始blinky為常駐範例，其有界smoke timeout不作正式案例pass；正式case host timeout一律失敗。
7. Tool／header／fixture資料上限與JSON／HTTP契約集中在data-contract，前後端不各自定義。
8. 計畫保留13個任務，沒有把空目錄／文件建立當產品完成。

## 尚需實作時查驗，無須使用者代查

- 固定QEMU／xPack組合是否可建置與執行；QEMU machine flags及DTB實際頻率。
- 本地SDK與FreeRTOS選定版本的完整hooks、事件參數與stream shutdown語意。
- user event編碼是否能保留所有case ID／phase／message ID；未支援格式需明確報錯。
- SVG／Tabulator固定套件版本的操作API、DOM、資料量與效能。
- 對真實trace驗證採用的CPU／latency／deadlock推論前提，不能只看手工fixture。

## 原始產品研究仍未完成

U01～U16保留在 [內網接續任務](../../references/baseline/research/內部AI-接續研究任務.md)。本POC為U01／U08／U12／U13／U14提供控制實驗與工具，不結清你們產品的驗收。

| 後續主題 | 保留原因 |
|---|---|
| 真正Flash／RAM、CPU%、每事件cycles、IRQ最差延遲 | 需要產品build與板上條件 |
| UART baud／DMA／bandwidth／host停頓／buffer loss | 初版semihost capture不能代表實體線路 |
| 動態裁剪／trigger／snapshot | 需要先確定不可刪事件與損失的分析能力 |
| Crash／reset保存、sleep／DVFS／SMP、電量 | 依實際RISC-V平台與產品需求驗證 |
| 雲端／本地保存、retention／retry／權限與TCO | 第一版僅本機服務，後端與成本另量測 |
| 離線HTML | 本版保留adapter介面；後續才實作完整離線運算與匯出 |

## 計畫驗證紀錄

本輪文件檢查結果保存於 [planning-verification.json](../../artifacts/planning-verification.json)。基準workspace-verification與docs/research/verification是各自當時版本的歷史紀錄，不拿其舊hash代表現在文件。
