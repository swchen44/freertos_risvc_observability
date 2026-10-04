/* SPDX-License-Identifier: GPL-2.0-or-later
 * API4, RV32 identity-mapped RAM, one cold capture window, fixed sysram-10.
 */
#include <qemu-plugin.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <inttypes.h>
#include "../qemu/live_timing.h"
#include "../qemu/poc-clock-api.h"
QEMU_PLUGIN_EXPORT int qemu_plugin_version=QEMU_PLUGIN_VERSION;
typedef struct { uint64_t pc; unsigned size; } Instruction;
static uint64_t begin_pc,end_pc,events,cycles,api_calls;
static unsigned active,windows,enabled;
static FILE *out;
static const void *handle;
static GPtrArray *instructions;
static void fail(const char *s) {fprintf(stderr,"live_cache: %s\n",s);exit(2);}
static void charge(uint64_t pc,uint64_t address,unsigned size,char op) {
 uint64_t c[5],total=0;
 if(++events>3000000 || timing_access(address,size,op,c)) fail("invalid access or event limit");
 for(unsigned j=0;j<5;j++) total+=c[j];
 cycles+=total;
 if(fprintf(out,"%"PRIu64",%"PRIu64",%u,%c,%"PRIu64",%"PRIu64",%"PRIu64",%"PRIu64",%"PRIu64"\n",
            pc,address,size,op,c[0],c[1],c[2],c[3],c[4])<0) fail("trace write");
 if(enabled) {qemu_plugin_poc_add_ns(handle,total*2);api_calls++;}
}
static void execute(unsigned cpu,void *arg) {
 if(cpu) fail("requires one vCPU");
 Instruction *i=arg;
 if(i->pc==begin_pc) {
  if(active || windows) fail("one window required");
  timing_reset();active=1;windows++;
 }
 if(i->pc==end_pc) {if(!active) fail("unmatched end");active=0;}
 if(active) charge(i->pc,i->pc,i->size,'I');
}
static void memory(unsigned cpu,qemu_plugin_meminfo_t info,uint64_t va,void *arg) {
 if(cpu) fail("requires one vCPU");
 if(!active) return;
 Instruction *i=arg;
 struct qemu_plugin_hwaddr *h=qemu_plugin_get_hwaddr(info,va);
 unsigned shift=qemu_plugin_mem_size_shift(info);
 if(!h || qemu_plugin_hwaddr_is_io(h) || shift>12) fail("unsupported memory access");
 charge(i->pc,qemu_plugin_hwaddr_phys_addr(h),1u<<shift,qemu_plugin_mem_is_store(info)?'W':'R');
}
static void translate(qemu_plugin_id_t id,struct qemu_plugin_tb *tb) {
 (void)id;
 for(size_t n=0;n<qemu_plugin_tb_n_insns(tb);n++) {
  struct qemu_plugin_insn *i=qemu_plugin_tb_get_insn(tb,n);
  Instruction *data=g_new(Instruction,1);
  *data=(Instruction){qemu_plugin_insn_vaddr(i),qemu_plugin_insn_size(i)};
  g_ptr_array_add(instructions,data);
  qemu_plugin_register_vcpu_insn_exec_cb(i,execute,QEMU_PLUGIN_CB_NO_REGS,data);
  qemu_plugin_register_vcpu_mem_cb(i,memory,QEMU_PLUGIN_CB_NO_REGS,QEMU_PLUGIN_MEM_RW,data);
 }
}
static void finish(qemu_plugin_id_t id,void *arg) {
 (void)id;(void)arg;
 if(active || windows!=1 || !events || fclose(out)) fail("incomplete capture");
 fprintf(stderr,"live_cache_complete events=%"PRIu64" cycles=%"PRIu64" api_calls=%"PRIu64"\n",events,cycles,api_calls);
 g_ptr_array_free(instructions,TRUE);
}
QEMU_PLUGIN_EXPORT int qemu_plugin_install(qemu_plugin_id_t id,const qemu_info_t *info,int argc,char **argv) {
 if(!info->system_emulation || strcmp(info->target_name,"riscv32") || info->system.smp_vcpus!=1 || argc!=4) return -1;
 uint64_t *pcs[]={&begin_pc,&end_pc};const char *keys[]={"begin=","end="};
 for(unsigned k=0;k<2;k++) {
  size_t n=strlen(keys[k]);char *tail;errno=0;
  if(strncmp(argv[k],keys[k],n)) return -1;
  *pcs[k]=strtoull(argv[k]+n,&tail,16);if(errno||*tail||!*pcs[k]) return -1;
 }
 if(begin_pc==end_pc || (strcmp(argv[2],"enabled=0")&&strcmp(argv[2],"enabled=1")) || strncmp(argv[3],"out=",4)) return -1;
 enabled=argv[2][8]=='1';handle=qemu_plugin_request_time_control();if(!handle) return -1;
 out=fopen(argv[3]+4,"wx");if(!out) return -1;
 if(fputs("pc,address,size,operation,l1i,l1d,l2,ram_read,ram_write\n",out)<0) fail("header");
 instructions=g_ptr_array_new_with_free_func(g_free);
 qemu_plugin_register_vcpu_tb_trans_cb(id,translate);
 qemu_plugin_register_atexit_cb(id,finish,NULL);return 0;
}
