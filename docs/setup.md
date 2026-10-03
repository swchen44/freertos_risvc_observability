# 已驗證的本機環境

2026-10-03，Apple Silicon macOS。精確版本、來源與 checksum 見 [toolchain lock](../tools/toolchain-lock.json)。QEMU 11.1.2、dtc 1.8.1 由 Homebrew 安裝；xPack GCC 15.2.0-1 archive 驗 SHA-256 後解壓到 `.tools/`。Python 3.13.2，開發套件見 `requirements-dev.lock`。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e . -r requirements-dev.lock
export PATH="$PWD/.tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin:$PATH"
git submodule update --init third_party/FreeRTOS
git -C third_party/FreeRTOS submodule update --init FreeRTOS/Source
.venv/bin/python -m psf_lab doctor
```

官方 demo 的工作副本放 `artifacts/local/upstream-demo/`；從固定 submodule 的 `FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC` 複製後，套用 [blinky patch](../firmware/upstream-patches/0001-blinky-toolchain.patch)。Patch 選 blinky，並將 compile／link code model 改為工具鏈支援的 medany。上游程式未修改。

```sh
make -C artifacts/local/upstream-demo/build/gcc CC=riscv-none-elf-gcc LD=riscv-none-elf-gcc SIZE=riscv-none-elf-size "FREERTOS_ROOT=$PWD/third_party/FreeRTOS/FreeRTOS" "DEMO_PROJECT=$PWD/artifacts/local/upstream-demo"
qemu-system-riscv32 -machine virt -bios none -nographic -kernel artifacts/local/upstream-demo/build/gcc/output/RTOSDemo.elf
```

以 Python subprocess 的 3 秒 timeout 限制觀察，收到 5 行 `Message received from task`。這只是常駐 blinky smoke，不是正式案例成功。ELF size：text 11052、data 28、bss 86062 bytes；尚未整合 SDK，不能當成 SDK overhead。

證據：[console](../artifacts/environment/upstream-smoke.log)、[完整 build](../artifacts/environment/upstream-build.log)、[QEMU DTB](../artifacts/environment/virt.dtb)。`fdtget -t u artifacts/environment/virt.dtb /cpus timebase-frequency` 為 10000000 Hz；後續 firmware 依此設定，而非沿用 demo 的 25 MHz。
