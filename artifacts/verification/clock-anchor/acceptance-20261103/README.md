# C2b 正式驗收與內網還原入口

2026-11-03。**正式16／16、20 anchors、review修正、完整還原及Git發布均已通過。** 完整解讀見[研究／操作報告](../../../../docs/clock-anchor-pilot.md)，本目錄保存可複查證據。[發布收據](verification/publication.json)記錄已核對的固定payload：POC `5b311de1`、root `d1410b5b`；後續metadata commit只補本收據及完成紀錄，不混稱capture來源。

| 入口 | 內容／使用方式 |
|---|---|
| [preview/analysis/report.md](preview/analysis/report.md) | 自動生成16-run報告、Mermaid、bounds／cost／code-size表 |
| [summary.json](preview/analysis/summary.json) | 16份獨立validation與四組對照的完整facts |
| [anchors.csv](preview/analysis/anchors.csv)／[comparisons.csv](preview/analysis/comparisons.csv) | 20筆anchors與比較明細，可用試算表查閱 |
| `preview/<run_id>/` | 真PSF、packet bytes、oracle、ELF／map、capture metadata |
| [preview-index.json](preview-index.json) | preview省略41個stream／歷史大檔及其原SHA；完整資料在restore包，preview不可直接當validator input |
| [restore/manifest.json](restore/manifest.json) | 1514個regular files、原bytes／SHA／mode、gzip與分卷SHA |
| [restore/restore-check.json](restore/restore-check.json) | 已實際還原1514檔、720494937 bytes的獨立receipt |
| [verification](verification/) | RED／GREEN、完整suite、runtime、review、code gate、實際還原／source驗證與移動後重驗 |
| [decisions.md](decisions.md) | 全部執行決策及代價；沒有deferred minor |
| [inventory.json](inventory.json) | 本次發佈artifact檔案SHA，inventory本身除外；最終receipt另記固定payload commit |

正式capture source `3cdb7794778bf608da6e86d189175c3cefb638b1`；獨立analysis／restore source `3e8a5fe27e1fbf922d7701b496b25ae021d84b3a`。後續metadata commit與原測試source分開記錄。

## 如何實際還原

先取得完整`poc-history` Git clone並保留history；本地root repo中的`poc`為nested repo／gitlink，主要實驗、程式與文件都在這裡。從POC root、Python環境可用時執行，output必須是尚不存在的新目錄：

```sh
PYTHONPATH=src .venv/bin/python - <<'PY'
from pathlib import Path
from tools.tcp.package_clock_anchor import verify_restore
print(verify_restore(
    Path('artifacts/verification/clock-anchor/acceptance-20261103/restore'),
    Path('artifacts/local/RESTORE_NEW'),
))
PY
```

還原只使用Python stdlib。各part最多64MiB，需保留全部1516parts及manifest；磁碟需容納約720MB原始資料與最大單檔gzip暫存。工具拒絕既有output、symlink／traversal、缺part、錯SHA、unsupported codec。完整資料在`RESTORE_NEW/runset/`；其餘tools／source路徑依manifest。

Manifest保留建立時`packaged-not-restore-verified`狀態；實際成功在獨立restore-check，不改寫原manifest。Manifest SHA：`9a55b8323647027839f3a10258c4cfa48013263a768b6f9a48419e53da7f1d75`。由原ignored位置移到本目錄後已重新驗全部1516parts，見[relocation receipt](verification/package-relocation.json)。

Outer restore不解包內層tar。執行者另外在獨立暫存目錄驗證完整patched QEMU source **75847項**與selected project source **1528項**，含mode／symlink target，見[source receipt](verification/task8-nested-source-restore.json)與[helper](verification/task8-verify-nested-sources.py)。Helper記錄原本機執行路徑，selected source比較對象是當時3e8a5fe2 snapshot，不能拿後續文件更新後的HEAD冒稱同一來源。

## 驗證邊界與後續

完整suite403個：398 passed／5 opt-in skipped；發布收尾再驗53.657s，見[task-done log](verification/task-8-tests.log)；另外明確啟用runtime5／5、0skip。全庫Ruff check與本輪format通過，**全庫format仍有10個baseline舊問題**。本輪沒有UI變更或新增browser驗收。

Host GCC distribution、GLib／system libraries與完整offline wheels未打包；資料／source還原不等於任意host可offline build。原absolute paths、Mac固定binary與Git ancestry需求保留；其他root／OS需重綁與重建新基準。未做cross-host驗收，未取得實機PMU／SDK CPU loading／UART結果。Web與離線HTML接合、三次重複、最新知識庫同步與產品source比對仍是後續。

修正前tools／runtime完整archive也在restore包內，保留失敗與中間檔；舊資料的context unknown_cause不列為正式驗收。決策細節及fresh review限制見[decisions](decisions.md)與[review](verification/final-review-astra.md)。
