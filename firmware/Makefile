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
ifneq ($(filter $(CASE),tcp_checksum1 tcp_checksum2 tcp_checksum3),)
LWIP := $(ROOT)/references/tcp/lwip
CFLAGS += -Itcp -I$(LWIP)/src/include -fno-strict-aliasing -DLWIP_CHKSUM_ALGORITHM=$(patsubst tcp_checksum%,%,$(CASE))
SRC += $(LWIP)/src/core/inet_chksum.c $(LWIP)/src/core/def.c
endif
ifneq ($(filter $(CASE),tcp_copy2 tcp_copy3 tcp_nocopy3 tcp_request_response),)
LWIP := $(ROOT)/references/tcp/lwip
CFLAGS += -Itcp_stack -I$(LWIP)/src/include -fno-strict-aliasing -ffile-prefix-map=$(ROOT)=/poc
CFLAGS += -DLWIP_CHKSUM_ALGORITHM=$(if $(filter tcp_copy2,$(CASE)),2,3)
CFLAGS += -DPOC_TCP_COPY=$(if $(filter tcp_nocopy3,$(CASE)),0,1)
SRC += $(wildcard $(LWIP)/src/core/*.c) $(wildcard $(LWIP)/src/core/ipv4/*.c)
endif
# Independent -Os experiments. Default firmware and downloaded lwIP stay unchanged.
TCP_VARIANT ?= baseline
ifeq ($(filter $(TCP_VARIANT),baseline layout checksum pbuf),)
$(error TCP_VARIANT must be baseline, layout, checksum or pbuf)
endif
LINKER := $(DEMO)/build/gcc/fake_rom.ld
ifeq ($(TCP_VARIANT),layout)
LINKER := tcp_stack/hot-layout.ld
endif
ifeq ($(TCP_VARIANT),checksum)
CFLAGS += -DPOC_ENDPOINT_CHECKSUM
SRC += tcp_stack/os_checksum.c
endif
ifeq ($(TCP_VARIANT),pbuf)
CFLAGS += -DPOC_PBUF_WALK
endif
ASM := $(PORT)/portASM.S $(DEMO)/build/gcc/start.S
ifeq ($(CASE),tcp_request_response)
CFLAGS += -DLWIP_STATS=1
endif
# Bounded experiment: only the checksum translation unit changes optimization.
CHECKSUM_OPT ?= Os
ifeq ($(filter $(CHECKSUM_OPT),Os O2),)
$(error CHECKSUM_OPT must be Os or O2)
endif
$(OUT)/inet_chksum.o: CFLAGS += -$(CHECKSUM_OPT)
OBJ := $(addprefix $(OUT)/,$(notdir $(SRC:.c=.o) $(ASM:.S=.o)))
VPATH := $(sort $(dir $(SRC) $(ASM)))
all: $(OUT)/firmware.elf $(OUT)/tasks.i $(OUT)/queue.i
$(OUT):
	mkdir -p $@
$(OUT)/%.o: %.c Makefile $(wildcard config/*.h port/*.h app/*.h app/cases/*.h) | $(OUT)
	$(CC) $(CFLAGS) -MMD -MP -c $< -o $@
$(OUT)/%.o: %.S Makefile | $(OUT)
	$(CC) $(CFLAGS) -MMD -MP -c $< -o $@
$(OUT)/firmware.elf: $(OBJ) $(LINKER)
	$(CC) $(CFLAGS) $(OBJ) -T$(LINKER) -Wl,--gc-sections,-Map,$(OUT)/firmware.map,--defsym=__stack_size=4096 --specs=nosys.specs -o $@
	$(SIZE) $@
$(OUT)/%.i: $(KERNEL)/%.c $(wildcard config/*.h port/*.h) | $(OUT)
	$(CC) $(CFLAGS) -E $< -o $@
-include $(wildcard $(OUT)/*.d)
.PHONY: all
