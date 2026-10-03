# M1：模擬、PSF Parser 與 Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 執行真實 RV32 FreeRTOS Queue 案例，取得 PSF、JSON、獨立 oracle 和可重跑的 pass／fail。

**Architecture:** 工具與 firmware 先建立可信時鐘及 capture，parser 另以既有 binary 測試起步。兩條路徑在 Queue harness 合流，來源、設定與結果全部可追查。

**Tech Stack:** Python 3.13、unittest、Ruff；QEMU TCG、RISC-V GCC、FreeRTOS 202411.00、本地 TraceRecorder；Make、semihosting。

**Spec:** [設計規格](../design/PSF-Lab-設計規格.md)；[共同契約](data-contract.md)

## Global Constraints

- 所有工作在 `~/git/percepio/poc`；`references/baseline/` 不改寫。
- RV32IMAC／ILP32、單 hart、M-mode；PSF v14 little-endian。
- 支援 desktop 64-bit `0x1FF1 / my_krnl / 1.0.0` 與 RV32 `0x1AA1 / FreeRTOS / 1.2.0`，不可混用 event table。
- SDK initialization 必須在 RTOS create 呼叫前；kernel 重新編譯使 hooks 生效。
- 正式 run 必須 clean commit；工具／upstream lock 驗證通過才能執行。
- 本文件的 test code 使用 unittest，測試檔均建立 `__init__.py`；不以 skip 當成實跑。

## Review Focus

1. 缺 GCC libc／kernel submodule → T1 preflight 明確失敗，不誤判 SDK。
2. Header 長度／entry count 耗盡資源 → T2 限制與截斷矩陣，不能無界配置。
3. 相同 event ID 不同平台 → T3 針對 0x20／0x25 解碼差異測試。
4. Clock 與 capture 自我驗證 → T4 DTB timebase、tick probe、獨立 byte count。
5. Oracle 缺漏或 QEMU timeout → T5 nonzero，保存原始 log／partial PSF。

## P1-T1：可執行的環境檢查與官方 demo

**Files**
- Create: `pyproject.toml`, `requirements-dev.lock`, `src/psf_lab/__init__.py`, `__main__.py`, `cli.py`, `doctor.py`, `provenance.py`。
- Create: `tests/__init__.py`, `tests/unit/__init__.py`, `tests/unit/test_doctor.py`, `tests/unit/test_provenance.py`。
- Create: `.gitmodules`, `third_party/FreeRTOS` gitlink, `tools/toolchain-lock.json`, `firmware/upstream-patches/0001-blinky-toolchain.patch`, `docs/setup.md`。
- Modify: `.gitignore` 加 `.tools/`、`.worktrees/`、`*.egg-info/`，保留 source lock 可追蹤；README 加 doctor 用法。

**Interfaces**
- Consumes: 現有 source manifest、上游固定 commits。
- Produces: `inspect_tools(required: tuple[str,...]) -> dict`，含 `ok`、`tools`、`missing`；`verify_sources(root: Path, lock: dict) -> dict`；`require_clean_tree(root: Path) -> str`。CLI 先只有 `doctor`。

- [ ] **Step 1：先寫 preflight 與 provenance 的失敗測試。** 在臨時 Git repo 測 clean／tracked 修改／untracked source，避免測試讀寫真專案。

```python
import unittest
from unittest.mock import patch
from psf_lab.doctor import inspect_tools

class DoctorTests(unittest.TestCase):
    def test_missing_qemu_is_explicit(self):
        with patch("psf_lab.doctor.shutil.which", return_value=None):
            result = inspect_tools(("qemu-system-riscv32",))
        self.assertFalse(result["ok"])
        self.assertEqual(result["missing"], ["qemu-system-riscv32"])
```

另在 `test_provenance.py` 建 `tempfile.TemporaryDirectory`、`git init`、以 `git -c user.name=Test -c user.email=test@example.invalid commit` 建 baseline；新增 `dirty.c` 後要求 `require_clean_tree` 丟 RuntimeError。Lock 的檔案 hash 不同也必須回 `ok=false`。

- [ ] **Step 2：建立最小 Python 專案並看測試紅燈。** `pyproject.toml` 使用 setuptools src layout、Python `>=3.13,<3.14`，Ruff target `py313`、rules `E,F,I,B`、line-length 100，排除 `references`／`third_party`／產物。當前正式 Python 支援只宣稱 3.13。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e . ruff
.venv/bin/python -m unittest tests.unit.test_doctor tests.unit.test_provenance -v
```

預期第一次失敗為尚未實作的模組／函式；固定實際安裝版本到 lock，之後重建使用 lock。安裝失敗需記錄原錯誤，不當成測試紅燈證據。

- [ ] **Step 3：實作檢查與 CLI。** 用 `shutil.which`、`subprocess.run` 參數陣列、timeout；不執行 shell 字串。只取得工具版本與必要資訊，不 dump 全部環境變數。

```python
# provenance.py 的 clean 判斷核心
status = subprocess.run(
    ["git", "status", "--porcelain=v1", "--untracked-files=all"],
    cwd=root, check=True, capture_output=True, text=True,
).stdout
if status:
    raise RuntimeError("Formal run requires committed, clean sources")
```

工具 lock 含 URL、版本、archive SHA-256、executable SHA-256、multilib、sysroot 和使用命令。被忽略的工具也必須與 lock 比對，clean Git 本身不夠。

- [ ] **Step 4：取得及固定上游，驗證未整合 SDK 的 demo。** FreeRTOS 用 submodule，鎖以下父 commit 及 kernel commit；先只取得必要 kernel submodule。下載 archive 驗 SHA-256 後才解壓，拒絕絕對路徑／`..`。

```sh
git submodule add https://github.com/FreeRTOS/FreeRTOS.git third_party/FreeRTOS
git -C third_party/FreeRTOS checkout 152cf36d6775bce6026a791845af12201aae703d
git -C third_party/FreeRTOS submodule update --init FreeRTOS/Source
git -C third_party/FreeRTOS/FreeRTOS/Source rev-parse HEAD
```

最後一行必須為 `dbf70559b27d39c1fdb68dfb9a32140b6a6777a0`。工具鏈選用研究中的 xPack `15.2.0-1` darwin-arm64，若執行時下載／相容性不同，先保存查核結果與替代版本 lock 再繼續。QEMU 以本機可安裝官方來源 package 為起點，保存實際精確版本與 checksum，不使用「latest」作重現條件。

使用 `shutil.copytree` 把固定上游 demo 複製到 `artifacts/local/upstream-demo/`，建立其 `build/gcc/output` 目錄，再用 `git apply --check`／`git apply` 套最小 patch，保留上游乾淨。每次重建使用新的或已核對乾淨副本，不重複套patch。Patch 選 blinky、調 GCC／LD／SIZE prefix、compile／link 都用 xPack 支援的 `medany`，其餘行為維持官方範例。Makefile 的 `FREERTOS_ROOT` 以絕對路徑 override；不要遺漏 VPATH／Common source。工具解壓至 `.tools/` 後將該版本 bin 加到本次執行環境的 PATH，`docs/setup.md` 寫明實際位置。取得以下證據：

```sh
riscv-none-elf-gcc --version
riscv-none-elf-gcc -print-multi-lib
riscv-none-elf-gcc -print-file-name=nano.specs
qemu-system-riscv32 --version
```

建置命令寫入 setup，從 POC 根目錄執行：

```sh
POC_FREERTOS_ROOT="$PWD/third_party/FreeRTOS/FreeRTOS"
make -C artifacts/local/upstream-demo/build/gcc CC=riscv-none-elf-gcc LD=riscv-none-elf-gcc SIZE=riscv-none-elf-size "FREERTOS_ROOT=$POC_FREERTOS_ROOT"
```

執行文件必須保存展開後命令。官方 blinky 是常駐程式，觀察到 queue／timer output 後用有限 timeout 結束 smoke；此 smoke 不當正式案例成功。把 `subprocess.run` 的TimeoutExpired作為有限觀察結束，仍檢查先前輸出；不能僅憑timeout認定範例有運作。

- [ ] **Step 5：測試、記錄並 commit。**

```sh
.venv/bin/python -m unittest tests.unit.test_doctor tests.unit.test_provenance -v
.venv/bin/ruff check .
.venv/bin/ruff format --check .
git add pyproject.toml requirements-dev.lock src tests tools .gitignore .gitmodules third_party firmware/upstream-patches docs/setup.md README.md
git commit -m "build: pin RISC-V environment and add preflight checks"
```

成功條件：工具完整、原始 demo 可建置與觀察預期輸出、來源可還原。尚未加入 SDK 不算 M1 完成。

## P1-T2：有邊界的 PSF binary framing

**Files**
- Create: `src/psf_lab/parser/__init__.py`, `binary.py`, `errors.py`；`tests/unit/test_binary.py`。
- Create: `fixtures/desktop/trace.psf`, `fixtures/desktop/manifest.json`，逐 byte 複製現有 baseline PSF。

**Interfaces**
- Consumes: bytes、[PSF 格式研究](../research/PSF格式與解析研究.md) header／metadata layout。
- Produces: `parse_binary(data, *, source_name="memory.psf", strict=True) -> dict`、`ParseError(code, offset, message)`，回共同契約的 raw envelope。

- [ ] **Step 1：寫真實 fixture 及截斷測試。**

```python
import unittest
from pathlib import Path
from psf_lab.parser.binary import parse_binary
from psf_lab.parser.errors import ParseError

class BinaryTests(unittest.TestCase):
    def test_desktop_boundaries(self):
        data = Path("fixtures/desktop/trace.psf").read_bytes()
        trace = parse_binary(data)
        self.assertEqual(trace["platform"]["word_bytes"], 8)
        self.assertEqual(trace["events"][0]["offset"], 152)
        self.assertEqual(len(trace["events"]), 309)
        self.assertEqual(trace["source"]["byte_length"], 7152)

    def test_truncated_header(self):
        with self.assertRaises(ParseError) as caught:
            parse_binary(bytes.fromhex("00465350"))
        self.assertEqual(caught.exception.code, "truncated_header")
```

Fixture SHA-256 必須為 `32f6421362bda37e3b91411afedb5df0c29741f99fe1df08389cf76e56f79d47`，manifest 註明 desktop mock RTOS。再加入 32-bit 手工 `struct.pack` fixture：32-byte header＋28-byte timestamp metadata＋3×4-byte entry table header；payload 長度由高 4 bits×base width 算，expected offset 手算。

- [ ] **Step 2：確認紅燈。** `python -m unittest tests.unit.test_binary -v`；預期缺 parser／ParseError，而不是 fixture 不見。

- [ ] **Step 3：實作逐段 bounds check。**

```python
# binary.py：每次讀取前檢查，不預先相信 count
if size > len(data) - offset:
    raise ParseError("truncated_payload", offset, "record exceeds input")
record_size = 8 + ((event_word >> 12) & 0xF) * word_bytes
semantic_id = event_word & 0xFFF
```

先驗 magic、版本、endian、base width／cores／schema 支援；entry count 上限 65,536、symbol bytes 上限 4,096、總 events 上限 200,000、檔案16 MiB。每個長度先以剩餘資料驗證，不直接配置宣告大小。Unsupported endian／core count／mode 回明確 code。Timestamp frequency 0 禁止時間分析；原始 ticks 仍保留。多 session 或垃圾 prefix 第一版拒絕，不掃描猜 session。

- [ ] **Step 4：加入 payload 各位置截斷、未知合法 ID、最大 word count、32／64-bit、nonzero string padding、錯 magic／version、宣告巨大 entry count 的表格測試。** Strict 在不完整 event 報錯；partial 只回完整 prefix 並列 issue。Header／metadata 不完整仍拒絕。合法未知 ID 留給語意層，不能當 corruption 丟掉。

```sh
python -m unittest tests.unit.test_binary -v
ruff check .
ruff format --check .
```

- [ ] **Step 5：保存 layout 測試與 fixture 來源，commit。** `git add src/psf_lab/parser tests/unit/test_binary.py fixtures/desktop`；`git commit -m "feat: parse bounded PSF v14 binary records"`。

## P1-T3：兩種 schema、JSON 與 decode CLI

**Files**
- Create: `src/psf_lab/parser/semantic.py`, `schemas/__init__.py`, `schemas/desktop.py`, `schemas/freertos.py`；`tests/unit/test_semantic.py`, `test_decode_cli.py`。
- Create: `docs/format-support.md`, `fixtures/desktop/expected.json`。
- Modify: `cli.py`, `__main__.py`；增加 decode 子命令。

**Interfaces**
- Consumes: `parse_binary` raw envelope。
- Produces: `parse_trace(data, *, source_name="memory.psf", strict=True) -> dict`；`resolve_kind(platform_name: str, event_id: int) -> str` 定義在 semantic.py，僅支援已知 schema。

- [ ] **Step 1：寫平台衝突與真實序列測試。**

```python
class SemanticTests(unittest.TestCase):
    def test_id_20_dispatches_by_platform(self):
        self.assertEqual(resolve_kind("my_krnl", 0x20), "task_ready")
        self.assertEqual(resolve_kind("FreeRTOS", 0x20), "task_delete")

    def test_desktop_sequence(self):
        trace = parse_trace(Path("fixtures/desktop/trace.psf").read_bytes())
        ids = [event["id"] for event in trace["events"]]
        self.assertEqual(ids[9:], [0x20, 0x25, 0x61, 0x52, 0x62, 0x25] * 50)
```

測試 import `unittest`、`Path` 及 `parse_trace/resolve_kind`。Counter expected 固定為 `list(range(50))`，欄位從解碼 `fields["counter"]` 取，不從 parser 寫 expected。附 schema table 每個已支援事件的 writer 檔案／行號。

- [ ] **Step 2：先跑 `python -m unittest tests.unit.test_semantic tests.unit.test_decode_cli -v` 確認未實作失敗。**

- [ ] **Step 3：實作 schema 派送與完整 JSON。**

```python
key = (raw["platform"]["platform_id"], raw["platform"]["name"], raw["platform"]["schema"])
# dispatcher 使用三元 key；不單靠 format version 或 event_id
```

解碼 name／create／delete／switch／ready／queue／mutex／priority／user event，依本地 writer 欄位與 params 數驗證。不支援 printf specifier 保留原文與參數並加 issue；不呼叫 Python `%` 解讀任意來源。名稱 NUL 後 bytes 留 raw。名稱晚到、地址重用建立 epoch；尚未證實生命週期標記 unknown。CLI 用 `json.dump(..., ensure_ascii=False, allow_nan=False)`。

- [ ] **Step 4：加入 sequence wrap `65535→0`、gap、timestamp 一次 wrap、時間相同、無法判定多 wrap、handle 超過 `2**53`、未知 handle／ID、restart 拒絕、錯 schema tests。** Single-core sequence wrap 不當 loss；時間回退未能由 counter 模型解釋時標記未知，不自行補算。用 subprocess 驗 decode CLI exit code 及輸出 JSON。

```sh
python -m unittest tests.unit.test_binary tests.unit.test_semantic tests.unit.test_decode_cli -v
python -m psf_lab decode fixtures/desktop/trace.psf --output artifacts/local/desktop-trace.json
ruff check .
ruff format --check .
```

- [ ] **Step 5：更新格式支援表並 commit。** `git add src tests docs/format-support.md fixtures/desktop/expected.json`；`git commit -m "feat: decode desktop and FreeRTOS schemas into JSON"`。

## P1-T4：可信時鐘、FreeRTOS hooks 與 binary capture

**Files**
- Create: `firmware/Makefile`, `firmware/config/FreeRTOSConfig.h`, `trcConfig.h`, `trcKernelPortConfig.h`, `trcStreamPortConfig.h`。
- Create: `firmware/port/clock.c`, `clock.h`, `semihost.c`, `semihost.h`, `trcStreamPort.c`, `trcStreamPort.h`, `recorder_port.h`, `finish.c`。
- Create: `firmware/app/main.c`, `oracle.c`, `oracle.h`, `case_api.h`, `cases/queue_baseline.c`, `cases/clock_probe.c`。
- Create: `tests/integration/__init__.py`, `test_clock_capture.py`, `tests/native/test_stream_port.c`；`docs/integration.md`。
- Create: `cases/queue_baseline.json`, `cases/clock_probe.json`；tool lock 增 timebase／QEMU flags。

**Interfaces**
- Consumes: T1 pin 的工具／upstream、T3 parser。
- Produces: `uint64_t poc_mtime(void)`、`void poc_case_run(void)` 每個 ELF 選一個 case、`void poc_oracle_finish(void)`；SDK 規定的 stream callbacks；`make -C firmware CASE=queue_baseline` 產生 `build/queue_baseline/firmware.elf/.map`。

- [ ] **Step 1：先寫 integration 驗收與 fake transport 的 C 測試。** Python integration 預期 PSF 可解碼、platform 正確、16 個收送 ID、`capture_complete` 可由 oracle 核對；clock_probe 量固定 100 RTOS ticks 的 mtime delta，先確認沒 ELF 時明確失敗。C 測試 mock semihost，分別回全部寫完、只剩一部分、全部剩餘與 error；用 host clang＋assert 執行，避免只測 Python 替身。

```c
/* tests/native/test_stream_port.c 的必要斷言形狀 */
int32_t written = -1;
mock_remaining_bytes = 3;
assert(xTraceStreamPortWriteData(payload, 8, 0, &written) == TRC_SUCCESS);
assert(written == 5); /* semihost SYS_WRITE 回傳尚未寫入數 */
```

- [ ] **Step 2：獨立取得 QEMU timebase，再設定 firmware。** 用 `-machine virt,dumpdtb=...` 保存 DTB，以 `dtc` 讀 `/cpus/timebase-frequency`；將 dtc 也納工具 lock。保存 DTB hash、頻率及來源；FreeRTOS tick 設1000 Hz，recorder 讀同一 mtime。不要以 PSF 自己宣告的 frequency 校驗自己。

```c
uint64_t poc_mtime(void) {
    volatile uint32_t *lo = (volatile uint32_t *)0x0200bff8u;
    uint32_t hi_a, low, hi_b;
    do {
        hi_a = lo[1]; low = lo[0]; hi_b = lo[1];
    } while (hi_a != hi_b);
    return ((uint64_t)hi_a << 32) | low;
}
```

application-defined hardware port 使用 low32、free-running increment、divisor1、已確認頻率；critical section 必須保存／還原原 MIE，不可一律開中斷。測 IRQ 原本關閉時進出仍關閉。

- [ ] **Step 3：最小 hooks、single-stream 與 Queue。** 本地 SDK source 從 `references/baseline/percepio/TraceRecorder` 建置；自訂 config／port include 優先。SDK 原型對照 File port，**不複製其 multistream flag**：

```c
traceResult xTraceStreamPortWriteData(
    void *data, uint32_t size, uint32_t channel, int32_t *written);
/* 單 core 只接受 channel 0；ReadData 設 *bytes_read=0。 */
```

先實作同步、bounded direct write，避免 CTI streaming task 擾動未定義；有 partial-write、zero-progress 時界定重試上限，失敗傳到 oracle。SYS_OPEN binary mode、SYS_WRITE remaining、SYS_CLOSE 都保存 error，輸出到 runner cwd 的固定 `trace.psf`／`oracle.json`，console 另外 UART。

`xTraceInitialize()`／`xTraceEnable(TRC_START)` 依 SDK startup 契約在 create 前完成；`configUSE_TRACE_FACILITY=1`、`TRC_CFG_FREERTOS_VERSION=TRC_FREERTOS_VERSION_11_1_0`。記錄 create／switch／queue／必要 user events，kernel 重新編譯。產生 `tasks.i`／`queue.i` 與 map 證明 hooks 生效。

Queue length4，producer/consumer 優先權2/3，IDs0..15，timeout為100 ticks；應用用固定陣列記 oracle，finish才輸出JSON，避免逐事件 semihost text I/O。SDK user event 以 `POC` channel、固定 phase＋整數 ID 表示 SEND／RECEIVE／COMPLETE；錯 return code 不記成功事件。收尾寫 completion、stop／close；若 SDK close 在 disable 中發生，要確認 completion 已寫入再 disable。

- [ ] **Step 4：執行 clock_probe 與 Queue 的開發驗收。** T5 runner 前，integration tests 用 `subprocess.run(..., cwd=temp_dir, timeout=30)` 執行以下參數陣列，保存展開命令；這些探索產物放 local/。

```python
elf = (root / "build/queue_baseline/firmware.elf").resolve()
command = [
    "qemu-system-riscv32", "-machine", "virt", "-cpu", "rv32",
    "-smp", "1", "-m", "128M", "-bios", "none", "-display", "none",
    "-monitor", "none", "-serial", "file:console.log",
    "-accel", "tcg,thread=single", "-icount", "shift=0,align=off,sleep=off",
    "-semihosting-config", "enable=on,target=native", "-kernel", str(elf),
]
subprocess.run(command, cwd=temp_dir, timeout=30, check=True)
```

`root` 為測試檔向上解析的 POC root、`temp_dir` 為測試的 TemporaryDirectory；clock_probe只替換case對应的ELF。實際採用 QEMU flags 必須在 `--help`／執行驗證，若版本不支援先記錄差異。Guest 最終用 virt finisher 結束；測試 clock delta 誤差不超過2 ticks 的 mtime counts，並報原始量測，不靠 host wall-clock。

```sh
python -m unittest tests.integration.test_clock_capture -v
ruff check .
ruff format --check .
```

- [ ] **Step 5：記錄安裝／hook／clock／capture 差異並 commit。** `git add firmware cases tests tools docs/integration.md`；`git commit -m "feat: capture FreeRTOS queue events on RISC-V QEMU"`。這時才具備正式 run 的 source baseline。

## P1-T5：正式 run 與獨立 Queue harness

**Files**
- Create: `src/psf_lab/runner.py`, `harness.py`；`tests/unit/test_runner.py`, `test_harness.py`；`tests/integration/test_queue_e2e.py`。
- Modify: `cli.py` 增 run／check；`runs/README.md`、`docs/requirements.md`、README。

**Interfaces**
- Consumes: clean sources、case JSON、ELF、`parse_trace`、oracle。
- Produces: `run_case(root, case_id, *, timeout_s=30.0) -> Path`、`check_case(case, trace, oracle) -> dict`，dict 固定 `{case_id, verdict, assertions, issues}`；assertion 有 `{name, expected, actual, passed}`。

- [ ] **Step 1：寫 independent oracle 的負向測試。** `test_harness.py` 手工組最小 trace／oracle，不調 decoder 建 expected；先讓 oracle少一個received ID，必須 fail。再讓 `complete=false`、缺 PSF marker、transport error，必須非 pass。

```python
result = check_case(case, trace, {**oracle, "complete": False})
self.assertNotEqual(result["verdict"], "pass")
self.assertIn("oracle_incomplete", result["issues"])
```

Runner tests mock `subprocess.run` timeout，確認留下 console／manifest、exit code4且無 pass。兩次同一 second 的 run_id 也不能覆寫：名稱追加 random suffix，用 exclusive mkdir；路徑只接受 allowlist case_id。

- [ ] **Step 2：跑 `python -m unittest tests.unit.test_runner tests.unit.test_harness -v`，確認紅燈。**

- [ ] **Step 3：實作 runner 與 assertions。** 先 clean check＋lock verify，再建立 run dir、從固定 source build、保存 ELF/map與hash，啟動 QEMU。PSF原封保存，JSON與oracle分開，缺檔寫missing。建置中與執行後再驗 source hash，確保沒有途中修改。

```python
# assertions 基準，expected IDs 來自 case.parameters.count
expected_ids = list(range(case["parameters"]["count"]))
ids_match = oracle["sent_ids"] == expected_ids and oracle["received_ids"] == expected_ids
```

再核對 PSF 的 SEND／RECEIVE application IDs 和成功 queue events、object lifecycle；不要求包含未保證的每個排程間隔。Run manifest 保存工具hash、casehash、config、ELF/map、完整參數、clock、start/end、exit、bytes、loss與完整性。

- [ ] **Step 4：先跑全體 unit tests／Ruff，commit 程式；再執行正式 Queue。**

```sh
python -m unittest discover -s tests/unit -t . -v
ruff check .
ruff format --check .
git add src tests runs/README.md docs README.md
git commit -m "feat: validate QEMU traces against independent queue oracle"
python -m psf_lab run queue_baseline
```

`run` 自動 parse＋check 並把實際 run 路徑印出；`check` 接受剛產生的run路徑，必須可獨立重做；integration test使用 `run_dir = run_case(root, "queue_baseline")` 回傳值傳入，不解析任意shell輸出。`test_queue_e2e` 使用臨時輸出根並呼叫相同 runner，明確禁止 skip。正式 run 寫入後工作目錄有新證據屬預期，下一個正式 run 前先 commit。

- [ ] **Step 5：審查 M1 證據並 commit。** 至少一份真實 Queue trace、16 IDs、正確schema／clock、完整結束、PSF hash、oracle及assertions。將 run artifacts、`docs/journal` 與「研究→證據」表 commit；只列已通過項目。

## M1 Gate

必須同時有 desktop fixture regression、真實 FreeRTOS hooks 證據、獨立 clock 校驗、Queue PSF／oracle／assertions、錯資料拒絕、unit／integration／Ruff結果。任何一項缺少都保留 M1 未完成，不進行第一版完成宣稱。

## 官方查核入口

- [固定版本 Makefile](https://github.com/FreeRTOS/FreeRTOS/blob/202411.00/FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC/build/gcc/Makefile)：原始 ABI／工具與來源清單，實作以 overlay 保存差異。
- [QEMU invocation](https://www.qemu.org/docs/master/system/invocation.html)：核對 machine、icount、semihosting flags；實際使用版本另鎖定。
