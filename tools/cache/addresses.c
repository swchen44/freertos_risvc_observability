/* SPDX-License-Identifier: GPL-2.0-or-later
 * Single-vCPU, bounded, guest-physical data capture for cache replay.
 * Arguments: pc_start=,pc_end=,data_start=,data_end= (hex),out=path
 */
#include <qemu-plugin.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
QEMU_PLUGIN_EXPORT int qemu_plugin_version = QEMU_PLUGIN_VERSION;
static uint64_t pc_start, pc_end, data_start, data_end, count;
static FILE *output;
static void fail(void) { fprintf(stderr,"cache capture failed\n"); exit(2); }
static void memory(unsigned cpu, qemu_plugin_meminfo_t info, uint64_t va, void *user) {
 (void)user;
 if(cpu!=0) fail();
 struct qemu_plugin_hwaddr *ha=qemu_plugin_get_hwaddr(info,va);
 if(!ha || qemu_plugin_hwaddr_is_io(ha)) return;
 uint64_t pa=qemu_plugin_hwaddr_phys_addr(ha);
 unsigned shift=qemu_plugin_mem_size_shift(info);
 if(shift>12) fail();
 unsigned size=1u<<shift;
 if(pa<data_start || pa>=data_end) return;
 if(size>data_end-pa || ++count>1000000) fail();
 if(fprintf(output,"%" PRIu64 ",%u,%c\n",pa,size,
            qemu_plugin_mem_is_store(info)?'W':'R')<0) fail();
}
static void translate(struct qemu_plugin_tb *tb, void *userdata) {
 (void)userdata;
 for(size_t i=0;i<qemu_plugin_tb_n_insns(tb);i++) {
  struct qemu_plugin_insn *insn=qemu_plugin_tb_get_insn(tb,i);
  uint64_t pc=qemu_plugin_insn_vaddr(insn);
  if(pc>=pc_start && pc<pc_end)
   qemu_plugin_register_vcpu_mem_cb(insn,memory,QEMU_PLUGIN_CB_NO_REGS,
                                    QEMU_PLUGIN_MEM_RW,NULL);
 }
}
static void finish(void *user) {
 (void)user;
 if(fclose(output)!=0) fail();
 fprintf(stderr,"cache_capture_complete=%" PRIu64 "\n",count);
}
QEMU_PLUGIN_EXPORT int qemu_plugin_install(qemu_plugin_id_t id,
 const qemu_info_t *info,int argc,char **argv) {
 const char *path=NULL; unsigned seen=0;
 if(!info->system_emulation || info->system.smp_vcpus!=1) return -1;
 for(int i=0;i<argc;i++) {
  if(!strncmp(argv[i],"out=",4)) { if(path) return -1; path=argv[i]+4; continue; }
  char *end; char *eq=strchr(argv[i],'=');
  if(!eq) return -1;
  errno=0; uint64_t value=strtoull(eq+1,&end,16);
  if(errno || end==eq+1 || *end || eq[1]=='-') return -1;
  unsigned bit=0;
  if(!strncmp(argv[i],"pc_start=",9)) { pc_start=value; bit=1; }
  else if(!strncmp(argv[i],"pc_end=",7)) { pc_end=value; bit=2; }
  else if(!strncmp(argv[i],"data_start=",11)) { data_start=value; bit=4; }
  else if(!strncmp(argv[i],"data_end=",9)) { data_end=value; bit=8; }
  else return -1;
  if(seen&bit) return -1;
  seen|=bit;
 }
 if(seen!=15 || !path || !*path || pc_start>=pc_end || data_start>=data_end) return -1;
 output=fopen(path,"wx"); if(!output) return -1;
 if(fputs("address,size,operation\n",output)<0) fail();
 qemu_plugin_register_vcpu_tb_trans_cb(id,translate,NULL);
 qemu_plugin_register_atexit_cb(id,finish,NULL);
 return 0;
}
