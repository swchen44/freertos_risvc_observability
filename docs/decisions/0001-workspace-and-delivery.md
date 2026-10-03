# 0001：POC 位置、輸入與交付方式

日期：2026-10-03。狀態：使用者已確認。

| 決策 | 使用者要求 | 影響 |
|---|---|---|
| 工作位置 | `~/git/percepio/poc` | 獨立 Git；實驗、文件與證據集中保存 |
| 輸入 | Q1=A，PSF；原來 PDF 是打錯字 | PDF 保留為研究依據，不做 PDF 上傳解析產品 |
| 第一版 | Q2=B，本機 Python 服務 | Python 分析與查詢；瀏覽器以 SVG＋JavaScript 呈現 |
| 後續 | 離線 HTML | 前端資料介面與 HTTP 解耦，尚未實作離線交付 |
| 品質 | unittest 與 Ruff；適當 skill review | 將語意測試、lint、瀏覽器操作分開驗收 |

套件、capture、工具鏈等技術細節由 agent 查證並提出建議；不重複詢問以上已確認事項。
