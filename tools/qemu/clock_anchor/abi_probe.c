/* Dynamic ABI capability smoke; does not claim clock alignment or TCP coverage. */
#include <qemu-plugin.h>
#include "poc-clock-anchor-api.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
QEMU_PLUGIN_EXPORT int qemu_plugin_version=QEMU_PLUGIN_VERSION;
static const void *handle;
static int began;
static int outside_cpu;
static void execute(unsigned cpu, void *arg) {
    (void)arg;
    if(cpu) exit(2);
    if(!began) {
        PocClockNote n={.struct_size=sizeof n,.kind=POC_CLOCK_BEGIN};
        qemu_plugin_poc_clock_note(handle,&n);
        n.kind=POC_CLOCK_END;qemu_plugin_poc_clock_note(handle,&n);
        began=1;
    }
}
static void translate(qemu_plugin_id_t id, struct qemu_plugin_tb *tb) {
    (void)id;
    for(size_t i=0;i<qemu_plugin_tb_n_insns(tb);i++)
        qemu_plugin_register_vcpu_insn_exec_cb(qemu_plugin_tb_get_insn(tb,i),execute,
                                             QEMU_PLUGIN_CB_NO_REGS,NULL);
}
static void finish(qemu_plugin_id_t id, void *arg) {
    (void)id;(void)arg;
    if(!began || !qemu_plugin_poc_clock_finish(handle,0)) exit(2);
    fputs("C2b ABI probe finished\n",stderr);
}
QEMU_PLUGIN_EXPORT int qemu_plugin_install(qemu_plugin_id_t id, const qemu_info_t *info,
                                          int argc, char **argv) {
    if(!info->system_emulation || strcmp(info->target_name,"riscv32")) return -1;
    PocClockConfig c={.struct_size=sizeof c,.abi_version=1,.expected_frequency_hz=10000000,
        .run_id="abi-control",.configuration="C",
        .qemu_sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        .elf_sha256="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        .profile_sha256="cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        .plugin_sha256="dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"};
    handle=qemu_plugin_request_time_control();
    if(argc>1) return -1;
    if(argc==1) {
        if(!strcmp(argv[0],"fault=abi")) c.abi_version=2;
        else if(!strcmp(argv[0],"fault=size")) c.struct_size--;
        else if(!strcmp(argv[0],"fault=handle")) handle=(void *)1;
        else if(!strcmp(argv[0],"fault=context")) outside_cpu=1;
        else return -1;
    }
    if(!qemu_plugin_poc_clock_configure(handle,&c)) {
        fputs("C2b ABI configure rejected\n",stderr);return -1;
    }
    if(outside_cpu) qemu_plugin_poc_add_ns_tagged(handle,2,1,0);
    qemu_plugin_register_vcpu_tb_trans_cb(id,translate);
    qemu_plugin_register_atexit_cb(id,finish,NULL);
    return 0;
}
