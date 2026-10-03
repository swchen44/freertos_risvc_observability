# 執行紀錄規範

目前沒有新 QEMU run。未來每次使用 `YYYYMMDDTHHMMSSZ-case-shortsha` 作 run_id，建立獨立子目錄；重跑不可覆寫。

| 檔案 | 必備內容 |
|---|---|
| `manifest.json` | run_id、UTC 時間、case、Git commit／dirty、source hash、工具版本、ISA／ABI、clock、capture、完整命令、輸入與輸出 SHA-256 |
| `result.md` | 目的、預期、觀察、判定、失敗原因、限制與下一步 |
| `console.log` | stdout／stderr、exit code、timeout；成功與失敗都保留 |
| `trace.psf` | 未改寫的收集結果；截斷也保留並標記 |
| `oracle.json` | 應用獨立計數、ID、狀態、完成與超時 |
| `trace.json` | parser 版本、schema、品質與解碼結果 |
| `assertions.json` | 預先定義 expected、觀察值、pass／fail／indeterminate |

資料缺失時明確列出 missing，不能捏造 placeholder trace／oracle。小型代表性 run 直接 commit；大型暫存放 `local/`，正式摘要記錄保存位置與 hash。不要將機密環境變數或憑證加入 log。

正式實驗開始前，所有建置輸入、案例、設定與工具程式必須已 commit，且 Git 工作目錄乾淨；manifest 記錄該 commit。先檢查再建立 run 產物。執行中若改動來源即作廢，修正並 commit 後用新的 run_id 重跑。臨時 dirty 探索只能放 local/ 並標為不可重現草稿，不能用來宣稱正式驗收。

## 已實作命令

`python -m psf_lab run queue_baseline` 要求乾淨 Git、固定 submodule 和工具 checksum，強制重新編譯後執行 QEMU。每次 run 保留 case、ELF、map、展開 hooks、PSF、oracle、JSON、assertions 和 manifest。`python -m psf_lab check RUN_DIRECTORY` 從 raw PSF／oracle 重做判定並核對原始 hash。host timeout／crash 的 exit code 為 4，不當案例成功。

正式 run 產物需 commit 後才可執行下一輪。整合測試用同一 runner 輸出到 TemporaryDirectory，仍要求原始碼乾淨，沒有 skip。

`python -m psf_lab suite --repeat 3` 一次執行七配置各三次，並做每輪三組比較。開始時仍需 clean source；suite session 只容許它以 exclusive mkdir 建立的輸出子目錄新增檔案，其他 tracked／untracked 變更、HEAD 或來源 hash 改變都拒絕。每次失敗也列入 attempts，不能漏掉 timeout。
