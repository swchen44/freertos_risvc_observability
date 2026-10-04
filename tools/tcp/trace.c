/* SPDX-License-Identifier: GPL-2.0-or-later
 * Phase-gated instruction and physical memory trace for bare-metal RV32.
 * Instruction VAs are identity-mapped guest RAM in this test (no MMU).
 */
#include <qemu-plugin.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#include <errno.h>
QEMU_PLUGIN_EXPORT int qemu_plugin_version=QEMU_PLUGIN_VERSION;
typedef struct { uint64_t pc; unsigned size; } Instruction;
static uint64_t begin_pc,end_pc,count;
static unsigned phase,active;
static FILE *out;
static void fail(void) { fprintf(stderr,"TCP trace failed\n"); exit(2); }
static void emit(uint64_t pc,uint64_t addr,unsigned size,char op) {
 if(addr<0x80000000ULL || addr+size>0x88000000ULL || ++count>3000000) fail();
 if(fprintf(out,"%u,%"PRIu64",%"PRIu64",%u,%c\n",phase-1,pc,addr,size,op)<0) fail();
}
static void exec(unsigned cpu,void *arg) {
 Instruction *i=arg;
 if(cpu) fail();
 if(i->pc==begin_pc) { if(active) fail(); active=1; phase++; }
 if(i->pc==end_pc) { if(!active) fail(); active=0; }
 if(active) emit(i->pc,i->pc,i->size,'I');
}
static void mem(unsigned cpu,qemu_plugin_meminfo_t info,uint64_t va,void *arg) {
 if(cpu) fail();
 if(!active) return;
 Instruction *i=arg;
 struct qemu_plugin_hwaddr *h=qemu_plugin_get_hwaddr(info,va);
 if(!h || qemu_plugin_hwaddr_is_io(h)) fail();
 unsigned shift=qemu_plugin_mem_size_shift(info);
 if(shift>12) fail();
 emit(i->pc,qemu_plugin_hwaddr_phys_addr(h),1u<<shift,
      qemu_plugin_mem_is_store(info)?'W':'R');
}
static void translate(struct qemu_plugin_tb *tb,void *user) {
 (void)user;
 for(size_t n=0;n<qemu_plugin_tb_n_insns(tb);n++) {
  struct qemu_plugin_insn *i=qemu_plugin_tb_get_insn(tb,n);
  Instruction *data=malloc(sizeof *data);
  if(!data) fail();
  *data=(Instruction){qemu_plugin_insn_vaddr(i),qemu_plugin_insn_size(i)};
  qemu_plugin_register_vcpu_insn_exec_cb(i,exec,QEMU_PLUGIN_CB_NO_REGS,data);
  qemu_plugin_register_vcpu_mem_cb(i,mem,QEMU_PLUGIN_CB_NO_REGS,QEMU_PLUGIN_MEM_RW,data);
 }
}
static void finish(void *user) {
 (void)user;
 if(active || fclose(out)) fail();
 fprintf(stderr,"tcp_trace_complete=%"PRIu64",phases=%u\n",count,phase);
}
QEMU_PLUGIN_EXPORT int qemu_plugin_install(qemu_plugin_id_t id,const qemu_info_t *info,int argc,char **argv) {
 (void)id;
 if(!info->system_emulation || info->system.smp_vcpus!=1 || argc!=3) return -1;
 if(strncmp(argv[0],"begin=",6) || strncmp(argv[1],"end=",4) || strncmp(argv[2],"out=",4)) return -1;
 char *end;
 errno=0; begin_pc=strtoull(argv[0]+6,&end,16); if(errno||*end||!begin_pc) return -1;
 errno=0; end_pc=strtoull(argv[1]+4,&end,16); if(errno||*end||!end_pc||end_pc==begin_pc) return -1;
 out=fopen(argv[2]+4,"wx"); if(!out) return -1;
 if(fputs("phase,pc,address,size,operation\n",out)<0) fail();
 qemu_plugin_register_vcpu_tb_trans_cb(id,translate,NULL);
 qemu_plugin_register_atexit_cb(id,finish,NULL);
 return 0;
}
