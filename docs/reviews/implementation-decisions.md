# 實作決策與代價

這份紀錄彙整 Native execution ledgers，保存未在對話逐項打斷確認的實作選擇。使用者已授權在指定 POC 實作，這些決定未擴張至 merge、push、部署或硬體操作。

| 決定 | 依據 | 代價／若判斷錯誤 |
|---|---|---|
| 在指定 `poc` 獨立 repo 的 `feat/psf-lab` 工作，不再建巢狀 checkout | 使用者要求實驗與文件集中在此處 | 平行隔離較少，以專用 repo 與 clean-source gate 補足 |
| 將計畫任務標題正規化為 Task N | task-start 工具需要此格式 | Markdown anchor 會改，當時沒有指向舊 anchor 的連結 |
| T1 下載時先寫獨立 T2 parser | 計畫依賴圖允許 | 真 RV32 fixture 到手後可能需調整，後續已驗證 |
| Ruff 排除研究 Markdown | 0.16.10 會格式化 code fences，避免改寫研究片段 | 文件程式片段不自動 format，實際 Python 仍查核 |
| FreeRTOS 以確切 commit 加 submodule | tag 不能當作 remote branch 使用 | 不符版本會被 commit check 拒絕，需要重新固定 |
| Stream adapter 完整寫完或有界失敗 | SDK direct commit 不處理短寫，header 失敗會無限重試 | 永久錯誤可能沒有 oracle；保留 partial PSF 與非零 exit |
| 保留 SDK 建立的 TzCtrl | 此版本即使關 stack monitor 仍建立該 task，不改 SDK | priority 1／delay 10 ticks 的 observer 會產生排程與事件成本 |
| 使用 M2 的正式 case IDs | 消除 allowlist 與 case 設定別名不一致 | 舊未公開別名不接受，沒有正式 run 使用它們 |
| 依已確認設計使用本地 ECharts／Tabulator | 使用者已選方向，prototype skill 的 CDN／重複確認預設不適用 | 視覺方向若需調整，可從真實 prototype 改；不改 data contract |
| 大型瀏覽器載入的 hang guard 30 秒 | 100k 載入實測超過原草案 5 秒；產品延遲門檻尚未指定 | 未來若要求更低延遲，需索引、載入 cache 或較低容量，不宣稱目前即時 |
| HTML／null／品質整合檢查集中在 T4 真實瀏覽器 | T3 保留 BigInt／reset／response unit tests，避免重複 DOM mocks | 問題發現延後一個緊接任務，已在交付前驗證 |

逐任務 commit 範圍與實際命令：

- [M1 ledger](execution/01-simulator-parser-queue.md)
- [M2 ledger](execution/02-cases-and-analysis.md)
- [M3 ledger](execution/03-local-dashboard.md)

計畫與原始研究快照的日期狀態保留；當前成果以 README、正式 suite 與 final review 紀錄為準。
