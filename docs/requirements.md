# 需求、進度與未完成事項

更新：2026-10-03。這是目前 POC 的狀態表，未執行事項不標成通過。

## 需求來源

[原始 README](../references/baseline/README.md) 的 R01～R27、N01～N12 與 [內部 AI 任務](../references/baseline/research/內部AI-接續研究任務.md) U01～U16 全數保留在參考快照。原始八類 MECE 與交叉依賴仍有效；新增 POC 將資料產生、解碼、驗證與呈現分層。

## 完成與待辦

| 項目 | 狀態 | 下一個可驗收成果 |
|---|---|---|
| 一篇知識庫與 push | 已完成，commit `63ac65685a796870804445e5d79b59c78054ce41` | POC 尚未同步至該知識庫 |
| POC 目錄與 Git | 本輪建立 | README、過程、決策、來源 manifest 與初始 commit |
| PSF／QEMU／UI 研究 | 已有研究與 review | 以實際模擬及正式 parser 驗證研究主張 |
| PSF／本機服務選擇 | 已確認 | 依此設計，PDF 僅保留研究用途 |
| 設計規格／實作計畫 | 使用者已要求寫計畫；三份子計畫已建立 | [計畫 review 與執行方式](plans/README.md)，尚未開始程式實作 |
| RISC-V＋FreeRTOS＋SDK | 未建置 | 可重跑 firmware、版本鎖定、ELF／map、時鐘證據 |
| 正常／異常案例 | 未執行 | 七個配置、PSF、獨立應用結果與判定 |
| PSF → JSON parser | 未實作 | desktop 64-bit 與 RV32 FreeRTOS 的分開 schema |
| Harness | 未實作 | 預先定義 expected、錯誤案例拒絕、可追查結果 |
| 本機 Dashboard | 未實作 | SVG 圖表、filters、table、timeline、CSV |
| unittest／Ruff／瀏覽器驗收 | 未執行產品測試 | 實際命令、結果與失敗證據 |
| 離線 HTML | 後續階段 | 第一版本機服務完成後，驗證離線資料來源 |
| 板上 CPU／IRQ／UART 等 | 留待內網與硬體 | 保留 U01～U16，不以 QEMU 結果結清 |

## 不遺漏的原研究主題

SDK 目的、功能與限制、FreeRTOS hook／是否改 kernel、安裝與 API、Flash／RAM、CPU loading／每事件成本、UART 介面／頻寬／資料率、buffer／loss、動態裁剪、雲端與本地、金額與維護成本、PDF 圖文、YouTube、官方案例、PSF 格式、時間與物件生命週期、Git／重現性、內網原始碼比對、完整 Markdown／Mermaid 及 MECE 檢查均保留。

QEMU 可以驗證指定軟體行為與資料流程；實體效能、最差 IRQ、電氣吞吐、實際產品載入與能源成本仍需要產品環境。未來新增發現要登錄需求／案例或 U 任務，不能只留在對話。

## M1 實作證據

環境、parser、FreeRTOS hooks／時鐘、Queue runner／獨立 oracle 已驗證。42 個 unit tests、2 個 capture integration、1 個 clean-run E2E，以及 native transport tests 通過。M2 對照案例及 M3 Dashboard 尚未完成。正式證據見 README／日誌。U01～U16 硬體產品研究仍依原狀態追蹤。
