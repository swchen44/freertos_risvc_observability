# C2b 能力盤點：來源與環境證據

範圍：2026-10-23 的唯讀來源研究。**沒有新guest執行、capture、build、anchor API或UI驗收。** 修改範圍A／B仍在等待使用者選擇，不能把本資料夾視為完整C2b runtime acceptance。

- `source-audit.json`：parent commit、14個來源hash、QEMU flags、現有binary version／hash、A02 manifest身分比較；只執行既有binary的`--version`。
- `existing-psf-clocks.json`：以專案Python重新解析保存的A02 baseline／pbuf PSF；包含clock、platform、quality及trace hash，沒有生成新PSF。
- `upstream-source-check.json`：從QEMU固定revision重取3份官方source，以system curl正常TLS驗證，逐byte比對現有保存快照。
- `system-python-probe-failed.txt`、`urllib-source-probe-failed.txt`：先前環境probe失敗與後續採用的執行方式；未修改環境或停用TLS驗證。
- `docs-check.json`：Markdown連結／圖片與原baseline hash驗證。
- `source-review.json`：背景研究agent的來源一致性核對；涵蓋sample／timestamp、phase、RV32格式大小與pending決策，不是runtime review。
- `completion.json`：此checkpoint的範圍與未完成項目；不是pilot的通過收據。
- `inventory.json`：此目錄其他各檔案大小與SHA-256。

研究文件在POC的`docs/research/c2b-qemu-clock-capabilities.md`與`c2b-sdk-anchor-capabilities.md`；接續checklist在`docs/plans/19-c2b-clock-anchor-pilot.md`。

新checkout可以檢視這些已保存資料；`.tools/`中的本機QEMU完整source／binary不由本checkpoint提供。需要重新build時，先依既有`tools/qemu/build-clock-probe.sh`與固定tarball SHA還原，不能將系統QEMU取代成相同研究binary。公司平台SDK／PMU／UART量測仍未執行。
