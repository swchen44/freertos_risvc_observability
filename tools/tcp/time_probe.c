/* SPDX-License-Identifier: GPL-2.0-or-later
 * Fixed-jump feasibility probe. NOT a cache, CPU, or per-load stall model.
 * Requires single-vCPU -icount shift=0 and no WFI/time warp before trigger.
 */
#include <qemu-plugin.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <inttypes.h>
QEMU_PLUGIN_EXPORT int qemu_plugin_version=QEMU_PLUGIN_VERSION;
static uint64_t trigger,delay_ns,insns,at_trigger,target_ns;
static unsigned fired;
static const void *clock_handle;
static FILE *receipt;
static void execute(unsigned cpu,void *arg) {
 if(cpu) exit(2);
 insns++;
 if((uint64_t)(uintptr_t)arg==trigger) {
  if(fired++) exit(2);
  at_trigger=insns;target_ns=insns+delay_ns;
  fprintf(stderr,"time_control_request insns=%"PRIu64" delay_ns=%"PRIu64" target_ns=%"PRIu64"\n",insns,delay_ns,target_ns);
  fflush(stderr);
  if(delay_ns) {
   qemu_plugin_update_ns(clock_handle,(int64_t)target_ns);
   fputs("time_control_update_queued\n",stderr);fflush(stderr);
  }
 }
}
#if QEMU_PLUGIN_VERSION >= 7
static void translate(struct qemu_plugin_tb *tb,void *user) {
 (void)user;
#else
static void translate(qemu_plugin_id_t id,struct qemu_plugin_tb *tb) {
 (void)id;
#endif
 for(size_t n=0;n<qemu_plugin_tb_n_insns(tb);n++) {
  struct qemu_plugin_insn *i=qemu_plugin_tb_get_insn(tb,n);
  qemu_plugin_register_vcpu_insn_exec_cb(i,execute,QEMU_PLUGIN_CB_NO_REGS,
       (void*)(uintptr_t)qemu_plugin_insn_vaddr(i));
 }
}
#if QEMU_PLUGIN_VERSION >= 7
static void finish(void *user) {
#else
static void finish(qemu_plugin_id_t id,void *user) {
 (void)id;
#endif
 (void)user;
 if(fired!=1) exit(2);
 if(fprintf(receipt,"{\"fired\":%u,\"delay_ns\":%"PRIu64",\"at_trigger\":%"PRIu64",\"target_ns\":%"PRIu64",\"instructions\":%"PRIu64"}\n",fired,delay_ns,at_trigger,target_ns,insns)<0||fclose(receipt)) exit(2);
}
static int number(const char *s,uint64_t *out,int base) {
 char *end;errno=0;if(!*s||*s=='-') return -1;
 *out=strtoull(s,&end,base);return errno||*end?-1:0;
}
QEMU_PLUGIN_EXPORT int qemu_plugin_install(qemu_plugin_id_t id,const qemu_info_t *info,int argc,char **argv) {
 (void)id;
 if(!info->system_emulation||info->system.smp_vcpus!=1||argc!=3) return -1;
 if(strncmp(argv[0],"trigger=",8)||strncmp(argv[1],"delay=",6)||strncmp(argv[2],"out=",4)) return -1;
 if(number(argv[0]+8,&trigger,16)||number(argv[1]+6,&delay_ns,10)||!trigger||delay_ns>10000000) return -1;
 clock_handle=qemu_plugin_request_time_control();if(!clock_handle) return -1;
 receipt=fopen(argv[2]+4,"wx");if(!receipt) return -1;
#if QEMU_PLUGIN_VERSION >= 7
 qemu_plugin_register_vcpu_tb_trans_cb(id,translate,NULL);
#else
 qemu_plugin_register_vcpu_tb_trans_cb(id,translate);
#endif
 qemu_plugin_register_atexit_cb(id,finish,NULL);return 0;
}
