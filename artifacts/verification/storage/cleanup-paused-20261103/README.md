# 暫停開發期間的空間清理與還原

2026-11-03：依使用者「先暫停一下，你清理一下空間」執行。**Task7 維持暫停，沒有實作 analysis 模組，也沒有執行正式 16-run。** Tasks1–6 已發布的遠端核對在本資料夾的 task6 publication JSON。

## 清理結果

| 項目 | 結果 |
|---|---|
| 已有 archive 的重複副本 | 移除 development O 與三次 Task6 runtime 目錄；刪除前逐檔核對 archive 的 SHA／大小 |
| 兩份失敗 QEMU source | `.tools/c2b-clock-20261102/qemu-9.2.0` 與 `-r2/qemu-9.2.0`；先完整封存、實際還原、逐檔驗證內容／mode／symlink，再刪原目錄 |
| 移除原目錄內檔案 | 151,979 個 regular files，logical bytes 合計 1,443,470,294；不含為驗證而建立後刪除的暫時還原副本 |
| 新保留的完整 source archive | 374,174,339 bytes，六份 parts，每份最多 67,108,864 bytes；另有完整逐檔 inventory |
| 當次腳本觀測可用空間增量 | 1,891,155,968 bytes，約 1.76 GiB；量測可能受其他系統活動影響，不等同純 logical bytes |
| 當次清理結束可用空間 | 約 4.0 GiB；Git 保存與系統活動會使之變動 |
| tracked 檔／唯一證據遺失 | 0／0 |
| 保留 | accepted R3 QEMU source／build／binary、legacy reference QEMU、GCC、active probe、兩個 candidate ELF、原始 archives、失敗 build logs／metadata／binary |

現用 tools manifest 的所有編譯依賴重新核對通過；兩個 QEMU 的 SHA 與 `--version` 通過，均為 9.2.0。完整回歸沒有在暫停期間重跑；產品程式碼沒有因清理改變。cleanup／restore Python 經 Ruff，還原指令的三個單元測試通過。

## 還原失敗 source

在 POC 根目錄執行，output 必須是不存在的新目錄：

```sh
python3 artifacts/verification/storage/cleanup-paused-20261103/restore.py \
  --label c2b-clock-20261102 \
  --output artifacts/local/restored-failed-qemu-1
python3 artifacts/verification/storage/cleanup-paused-20261103/restore.py \
  --label c2b-clock-20261102-r2 \
  --output artifacts/local/restored-failed-qemu-2
```

`restore.py` 先核對 inventory、每一份 part 與合併 archive SHA，再檢查 tar paths，最後實際還原所有檔案並比對完整 inventory。會保留上游 symlink 的原始 target（含 X11 link），不會透過 symlink 解壓寫檔。既有 output、壞 part、缺 part 或 traversal 均拒絕；失敗輸出保留。

還原後 source 位於各 output 下的 `qemu-9.2.0/`。如果需要恢復舊 build 的絕對路徑，先確認原 source 目錄仍不存在，再將這個子目錄移回相應的 `.tools/<label>/`。本包是歷史 source 還原，不宣稱失敗 build 變成成功，也不代表其他 host 已通過編譯驗收。

```sh
python3 artifacts/verification/storage/cleanup-paused-20261103/test_restore.py -v
```

## 接手點

- Task7 BASE：`11885222eaf5f4e15af80b98a708db318b8a43be`。
- `task7-test-draft.py.txt`：原本尚未提交的 RED 測試，完整保存；以文字副檔名避免未完成 import 影響已通過的 test suite。
- `task7-red.log`：缺少 `clock_anchor_analysis` 的預期 RED。
- `progress-ledger.md`：Tasks1–6 與暫停決策；Task7 尚未完成。
- 恢復開發時先將 draft 複製回 `tests/unit/test_clock_anchor_analysis.py`，再按既有 Task7 brief 實作；不重跑已完成的 Tasks1–6。

`cleanup.py` 是本次一次性執行腳本，看到既有 receipt 就拒絕重跑。`receipt.json`／`summary.json`／inventory 保存原目錄、分卷、SHA、移除與還原結果；`paused-cleanup.log` 和 restore tests log 保存實際執行輸出。
