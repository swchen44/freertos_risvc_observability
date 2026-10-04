ROOT := $(abspath ..)
CASE ?= queue_baseline
TOOLCHAIN ?= $(ROOT)/.tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin
CC := $(TOOLCHAIN)/riscv-none-elf-gcc
SIZE := $(TOOLCHAIN)/riscv-none-elf-size
KERNEL := $(ROOT)/third_party/FreeRTOS/FreeRTOS/Source
DEMO := $(ROOT)/third_party/FreeRTOS/FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC
SDK := $(ROOT)/references/baseline/percepio/TraceRecorder
OUT := $(ROOT)/build/$(CASE)
PORT := $(KERNEL)/portable/GCC/RISC-V
INC := -Iconfig -Iport -Iapp -I$(KERNEL)/include -I$(PORT) -I$(PORT)/chip_specific_extensions/RV32I_CLINT_no_extensions -I$(DEMO) -I$(SDK)/include -I$(SDK)/kernelports/FreeRTOS/include
CFLAGS := $(INC) -DPOC_CASE='"$(CASE)"' -march=rv32imac_zicsr -mabi=ilp32 -mcmodel=medany -Os -g3 -ffunction-sections -fdata-sections -nostartfiles --specs=nano.specs
CASE_SRC := $(CASE)
ifneq ($(filter $(CASE),logger_bad logger_fixed),)
CASE_SRC := logger
CFLAGS += -DPOC_LOGGER_FIXED=$(if $(filter logger_fixed,$(CASE)),1,0)
endif
ifneq ($(filter $(CASE),inversion inheritance),)
CASE_SRC := inversion
CFLAGS += -DPOC_USE_MUTEX=$(if $(filter inheritance,$(CASE)),1,0)
endif
ifneq ($(filter $(CASE),deadlock_abba ordered_locks),)
CASE_SRC := deadlock
CFLAGS += -DPOC_ABBA=$(if $(filter deadlock_abba,$(CASE)),1,0)
endif
SRC := $(KERNEL)/tasks.c $(KERNEL)/queue.c $(KERNEL)/list.c $(KERNEL)/portable/MemMang/heap_4.c $(PORT)/port.c $(wildcard $(SDK)/*.c) $(SDK)/kernelports/FreeRTOS/trcKernelPort.c $(wildcard port/*.c) $(wildcard app/*.c) app/cases/$(CASE_SRC).c
ASM := $(PORT)/portASM.S $(DEMO)/build/gcc/start.S
OBJ := $(addprefix $(OUT)/,$(notdir $(SRC:.c=.o) $(ASM:.S=.o)))
VPATH := $(sort $(dir $(SRC) $(ASM)))
all: $(OUT)/firmware.elf $(OUT)/tasks.i $(OUT)/queue.i
$(OUT):
	mkdir -p $@
$(OUT)/%.o: %.c Makefile $(wildcard config/*.h port/*.h app/*.h app/cases/*.h) | $(OUT)
	$(CC) $(CFLAGS) -MMD -MP -c $< -o $@
$(OUT)/%.o: %.S Makefile | $(OUT)
	$(CC) $(CFLAGS) -MMD -MP -c $< -o $@
$(OUT)/firmware.elf: $(OBJ)
	$(CC) $(CFLAGS) $(OBJ) -T$(DEMO)/build/gcc/fake_rom.ld -Wl,--gc-sections,-Map,$(OUT)/firmware.map,--defsym=__stack_size=4096 --specs=nosys.specs -o $@
	$(SIZE) $@
$(OUT)/%.i: $(KERNEL)/%.c $(wildcard config/*.h port/*.h) | $(OUT)
	$(CC) $(CFLAGS) -E $< -o $@
-include $(wildcard $(OUT)/*.d)
.PHONY: all
