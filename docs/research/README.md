# PSF、RISC-V 模擬與 Dashboard：下一階段研究

更新日期：2026-10-03。這份文件記錄已查到的事實、使用者新增要求、設計選項與驗收方向。**目前正在研究與釐清設計，尚未建立新的模擬 firmware、Python decoder、harness 或 Dashboard。**

原始研究：[完整研究報告](../../references/baseline/research/FreeRTOS-RISC-V-Observability-研究報告.md)。要求與過程：[根 README](../../references/baseline/README.md)。產品驗證：[內部 AI 接續任務](../../references/baseline/research/內部AI-接續研究任務.md)。

## 1. 已確定的要求

使用者要用已下載的 SDK、PDF 與官方案例，建立可以實際驗證研究結論的環境：RISC-V 模擬器執行 FreeRTOS 和 SDK，正常／異常案例產生 PSF，Python 解析成 JSON，harness 檢查案例預期，最後用互動 HTML 呈現資料。

- 現有研究已依要求合併成一篇知識庫，完成 push：commit `63ac65685a796870804445e5d79b59c78054ce41`。這是原研究的保存基準，新工作在本資料夾接續。
- 使用者已指定 `~/git/percepio/poc`，本輪已建立獨立 Git、目錄與文件；firmware／parser／UI 尚未實作。
- 不購買 Percepio Tracealyzer；研究其公開功能與操作圖片，實作可驗證的分析功能。
- Python 必須加入 **`unittest` 與 `ruff`**。測試需要驗證資料語意與案例結果。
- Dashboard 要有 input、filters、views、詳細 hover、表格排序／欄寬／欄位移動、時間軸互動與篩選結果 CSV 匯出。
- 使用 Mermaid、清楚的 Markdown、API／來源連結；更新已完成與未完成事項。
- 使用者指定 `grilling`、要求設計師協作與適當 skill review，並要求不要猜意圖。

## 2. 查證文件

| 文件 | 研究目的 |
|---|---|
| [PSF 格式與解析研究](PSF格式與解析研究.md) | 由 recorder 寫入程式、XML 與既有 binary，確認欄位、版本、事件語意及解析限制 |
| [RISC-V 模擬環境研究](RISC-V模擬環境研究.md) | 官方 FreeRTOS／QEMU 起點、ISA／ABI、timer、UART、capture 與功能驗證邊界 |
| [Dashboard 功能與設計研究](Dashboard功能與設計研究.md) | 官方 UI／filter 證據、免費套件、離線限制、資料契約與互動驗收 |
| [獨立 review 紀錄](review-record.md) | 審查方法、已修正項目、尚無足夠證據下結論的部分 |

## 3. 使用者已確認的選擇

使用者已回答 Q1=A、Q2=B，並明確更正「PDF 轉 HTML」是筆誤。

| 項目 | 確認結果 | 設計影響 |
|---|---|---|
| 輸入 | PSF → 互動 Dashboard HTML／SVG＋專業 JavaScript | PDF 作為研究與案例參考；不建立 PDF 上傳／擷取功能 |
| 第一階段交付 | 本機 Python 服務 | Python 負責解析、分析與資料查詢；瀏覽器負責圖表與操作 |
| 後續方向 | 之後再改成離線 HTML | 現在把 JavaScript 視圖、資料契約與 HTTP 存取分開，讓後續能接離線資料來源 |

工具鏈、capture、套件、手勢與測試細節由 agent 根據來源提出具體方案。新的書面設計見 [PSF Lab 設計規格](../design/PSF-Lab-設計規格.md)。

## 4. 建議的工作拆分

以下是待 review 的方向，還不是已核准的實作規格。

| 子工作 | 輸入 | 可獨立驗收的輸出 | 前置條件 |
|---|---|---|---|
| 格式解析 | 真實 PSF、對應 recorder source／事件 schema | 保留 raw 證據及語意的 JSON、明確錯誤與完整性狀態 | 決定支援的版本、platform、32／64-bit 與封裝 |
| 模擬 firmware | 固定版本的 RISC-V 模擬器、FreeRTOS、SDK、案例 | ELF／map、執行記錄、PSF、獨立應用結果 | 時鐘與 hooks 可驗證；capture 方法確定 |
| Harness | 案例規格、PSF、JSON、應用結果 | 可重複的 pass／fail、失敗原因、版本與原始 artifact | parser 與案例的驗收語意一致 |
| Dashboard | 已驗證 JSON 與品質資訊 | 本機 Python 服務、HTML／SVG＋JavaScript、篩選後 CSV | PSF 輸入與本機服務已確認；具體設計待 review |

PSF 的原始欄位、解析後事件與衍生統計應能分別追查。事件遺失、未知事件或時鐘無效時，要保留不能判斷的區間；不可因圖表能畫出來就宣稱分析正確。

## 5. 案例提案

建議先做一個正常基準與三組異常／修正對照，共七個執行配置。這是從現有 PDF 與研究案例提出的控制實驗，不代表使用者產品已出現這些問題。

| 案例 | 預期證據 | 可參考的既有研究 | 判斷原則 |
|---|---|---|---|
| 正常 task／queue 基準 | 建立、ready、switch、send／receive、完成事件及 message ID | 主報告第 12.6、22 節 | producer／consumer 計數與 ID 一致，事件生命週期及時間可解釋 |
| Logger 干擾／改善 | 相同 request 工作下的搶佔與 response time | 第 22 節 C01 | 以應用 request 邊界與 RTOS 事件對照，execution／response 分開 |
| Priority inversion／inheritance 對照 | 高、中、低優先權 task 的等待及執行順序 | 第 22 節 C03 | 明確控制同步物件與啟動順序；驗證繼承事件和實際排程 |
| Deadlock／固定鎖順序對照 | 已取得的鎖、等待關係、進度停止或完成 | 第 22 節 C03 | 區分有完整持有／等待證據的循環，與僅憑長時間沒有事件的猜測 |

每組需要可終止的實驗、明確的觀察窗口與獨立結果。不能依賴任意 sleep 期待偶然出現排程，也不能由 decoder 自己生成 expected JSON 再自行宣稱通過。

Starvation／jitter、heap 趨勢、buffer overflow／裁剪與 UART 壓力，保留為後續擴充候選及既有 U 任務，不在沒有測量時標成完成。

## 6. Python 測試與 Ruff 驗收

### 必備的測試層次

| 層次 | 必須檢查的內容 |
|---|---|
| `unittest`：binary 解析 | 已知 header／payload、32／64-bit、平台事件表、truncation、unsupported version、unknown event、字串 NUL、offset 與原始 bytes 保留 |
| `unittest`：時間與物件 | counter wrap、sequence gap、trace restart、未知／重用 handle、object lifecycle；對無法還原的時間回報限制 |
| `unittest`：分析與輸出 | running／ready／blocked 的界線、選取窗口裁切、loss 區間、空資料、JSON 精度、CSV escaping 與篩選一致性 |
| 端到端 harness | 同一案例的 firmware→PSF→JSON→assertions；附獨立應用結果、結束 marker、預期事件序列及已固定的版本 |
| 瀏覽器驗收 | 真正操作 filter、表格排序／欄寬／移動、hover、timeline、reset 與 CSV；以實際匯出的內容比對畫面選取資料 |

Python 測試不能替代 JavaScript／瀏覽器互動驗收。Ruff 檢查也不能證明 binary 解析與統計語意正確。

### 實作完成後的預定檢查命令

以下命令是新專案的驗收要求，目前尚未執行新專案測試：

```sh
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
```

新專案的 `pyproject.toml` 會固定 Python／Ruff 設定及檢查範圍，測試模組保留 `__init__.py` 以避免不同 Python 版本的 discovery 差異。上游 SDK／FreeRTOS 原始碼與產生檔案分別保存，不用 Ruff 改寫其來源。需要 QEMU 的整合測試會提供明確命令、依賴缺失訊息及執行結果，不能以 skip 當成模擬已通過。

本機已確認有 Python 3.13 與 Ruff 0.15.13。這不代表內網環境相同；正式支援版本與依賴會寫入實作規格。

參考：[Python unittest](https://docs.python.org/3/library/unittest.html)、[Ruff configuration](https://docs.astral.sh/ruff/configuration/)、[Ruff formatter](https://docs.astral.sh/ruff/formatter/)。

## 7. Review 的分工與狀態

| 方法／skill | 要檢查什麼 | 目前狀態 |
|---|---|---|
| `grilling` | 真正的歧義、決策依賴、未說明的假設 | Q1／Q2 已回答；具體設計以書面規格確認 |
| `brainstorming` | 架構、子工作邊界、可驗收結果與方案取捨 | 設計研究中，尚未進入實作 |
| `frontend-design`／`web-design-engineer` | 資料到視圖的操作流程、視覺層級、互動與可讀性 | 設計代理進行研究；沒有宣稱已完成 UI |
| `requesting-code-review` | 獨立審查實作、資料語意、錯誤處理及測試缺口 | 本輪研究 review 完成並修正；正式程式碼 review 待實作後執行 |
| `verification-before-completion` | 完成宣稱是否有最新可讀取的測試／artifact 證據 | 每階段驗收時執行 |

## 8. 模擬結果的 boundary

QEMU 可用於執行 RISC-V firmware、驗證 FreeRTOS 行為、hooks、資料格式與指定控制實驗。`icount` 能以指令計數推動虛擬時間，但官方明確說明它不提供 cycle-accurate emulation；模擬結果無法直接填入你們實體晶片的每事件 cycles、CPU overhead、UART 電氣吞吐或最差 IRQ 延遲。

保留三種時間的標籤：模擬 guest 的時間、host 跑模擬的耗時、產品實體量測時間。是否增加模擬條件下的 A/B 指標，仍需先定義分母、時鐘與工作量。

來源：[QEMU TCG Instruction Counting](https://www.qemu.org/docs/master/devel/tcg-icount.html)。產品量測仍保留 [U02～U05 等接續任務](../../references/baseline/research/內部AI-接續研究任務.md)。

## 9. 新需求的 MECE 與狀態檢查

沿用主報告八個分類，只把新增 N01～N12 各登記一次；原 R／U 編號與產品未完成事項保留。下表是主要歸屬，不移除跨模組依賴。

| 原分類 | 本輪主要歸屬 | 交叉依賴 |
|---|---|---|
| M2 平台與 SDK 接合 | N05 | 校時、capture 與後續效能量測 |
| M6 分析、案例與問題改善 | N03、N06、N07、N08、N09、N10 | parser、案例、oracle、UI 共同資料語意 |
| M7 部署與金額成本 | N11 | 自製軟體仍有開發與維護成本 |
| M8 研究交接與運作管理 | N01、N02、N04、N12 | Git、skills review、品質檢查與 artifact |

M1／M3／M4／M5 本輪沒有新增獨立 N 編號；原有觀測邊界、板上 CPU／Flash／RAM、UART、loss／裁剪等要求仍由 R／U 對照追蹤。PSF、模擬與 Dashboard 的研究完成，不會自動結清產品 U01～U16。

本輪文件檢查、PSF probe 與 Mermaid 結果：[verification.json](verification.json)。PSF 探測原始輸出：[desktop-psf-probe.log](desktop-psf-probe.log)。

目前 POC 進度以 [POC README](../../README.md) 為準；本文件承接研究，來源快照維持歷史內容。
