/* SPDX-License-Identifier: GPL-2.0-or-later
 * QEMU 9.2/API4 nano probe. Count requested budgets independently of delivery.
 */
#include <qemu-plugin.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <inttypes.h>
#ifdef POC_RELATIVE
#include "../qemu/poc-clock-api.h"
#endif
QEMU_PLUGIN_EXPORT int qemu_plugin_version=QEMU_PLUGIN_VERSION;
static uint64_t trigger,begin_pc,end_pc,insns,start_insns;
static unsigned enabled,phase,active,count,api_calls;
static struct qemu_plugin_register *regs[4];
static GByteArray *bytes;
static const void *handle;
static FILE *out;
static const unsigned delays[5]={10,20,50,100,1000};
static void fail(const char *msg) {fprintf(stderr,"clock_nano: %s\n",msg);exit(2);}
static void init(qemu_plugin_id_t id,unsigned cpu) {
 (void)id;if(cpu) fail("requires one vCPU");
 const char *names[4]={"a0","a1","a2","a3"};
 GArray *all=qemu_plugin_get_registers();
 for(unsigned j=0;j<all->len;j++) {
  qemu_plugin_reg_descriptor *r=&g_array_index(all,qemu_plugin_reg_descriptor,j);
  for(unsigned k=0;k<4;k++) if(!strcmp(r->name,names[k])) regs[k]=r->handle;
 }
 g_array_free(all,TRUE);bytes=g_byte_array_new();
 for(unsigned k=0;k<4;k++) if(!regs[k]) fail("missing RV32 argument register");
}
static uint32_t reg(unsigned n) {
 g_byte_array_set_size(bytes,0);
 if(qemu_plugin_read_register(regs[n],bytes)!=4) fail("register read");
 uint32_t v;memcpy(&v,bytes->data,4);return GUINT32_FROM_LE(v);
}
static void count_instruction(unsigned cpu,void *data) {
 (void)data;if(cpu) fail("extra vCPU");insns++;
}
static void begin(unsigned cpu,void *data) {
 (void)cpu;(void)data;
 if(active||phase>=5||reg(0)!=phase) fail("begin sequence");
 active=1;count=0;api_calls=0;start_insns=insns;
}
static void end(unsigned cpu,void *data) {
 (void)cpu;(void)data;
 if(!active||reg(0)!=phase||count!=1000) fail("end sequence");
 if(fprintf(out,"%s{\"id\":%u,\"requests\":%u,\"requested_ns\":%u,\"insns\":%"PRIu64",\"api_calls\":%u}",phase?",":"",phase,count,delays[phase]*count,insns-start_insns,api_calls)<0) fail("receipt");
 fflush(out);active=0;phase++;
}
static void execute(unsigned cpu,void *data) {
 (void)data;if(cpu||!active) fail("request outside phase");
 uint64_t anchor=reg(0)|((uint64_t)reg(1)<<32);
 unsigned delay=reg(2),id=reg(3);
 if(id!=phase||delay!=delays[id]||count>=1000) fail("request sequence");
 count++;
 if(enabled) {
#ifdef POC_RELATIVE
  (void)anchor;
#ifdef POC_BURST
  for(unsigned j=0;j<10;j++) {qemu_plugin_poc_add_ns(handle,delay/10);api_calls++;}
#else
  qemu_plugin_poc_add_ns(handle,delay);api_calls++;
#endif
#else
  qemu_plugin_update_ns(handle,(int64_t)(anchor+delay));api_calls++;
#endif
 }
}
static void translate(qemu_plugin_id_t id,struct qemu_plugin_tb *tb) {
 (void)id;
 for(size_t n=0;n<qemu_plugin_tb_n_insns(tb);n++) {
  struct qemu_plugin_insn *i=qemu_plugin_tb_get_insn(tb,n);
  uint64_t pc=qemu_plugin_insn_vaddr(i);
  qemu_plugin_register_vcpu_insn_exec_cb(i,count_instruction,QEMU_PLUGIN_CB_NO_REGS,NULL);
  if(pc==trigger) qemu_plugin_register_vcpu_insn_exec_cb(i,execute,QEMU_PLUGIN_CB_R_REGS,NULL);
  if(pc==begin_pc) qemu_plugin_register_vcpu_insn_exec_cb(i,begin,QEMU_PLUGIN_CB_R_REGS,NULL);
  if(pc==end_pc) qemu_plugin_register_vcpu_insn_exec_cb(i,end,QEMU_PLUGIN_CB_R_REGS,NULL);
 }
}
static void finish(qemu_plugin_id_t id,void *data) {
 (void)id;(void)data;
 if(phase!=5||active) fail("incomplete phases");
 if(fputs("]}\n",out)<0||fclose(out)) fail("receipt close");
 g_byte_array_free(bytes,TRUE);
}
QEMU_PLUGIN_EXPORT int qemu_plugin_install(qemu_plugin_id_t id,const qemu_info_t *info,int argc,char **argv) {
 if(!info->system_emulation||info->system.smp_vcpus!=1||argc!=5) return -1;
 uint64_t *pcs[3]={&trigger,&begin_pc,&end_pc};
 const char *keys[3]={"trigger=","begin=","end="};
 for(unsigned i=0;i<3;i++) {
  size_t n=strlen(keys[i]);char *tail;errno=0;
  if(strncmp(argv[i],keys[i],n)) return -1;
  *pcs[i]=strtoull(argv[i]+n,&tail,16);if(errno||*tail||!*pcs[i]) return -1;
 }
 if(strcmp(argv[3],"enabled=0")&&strcmp(argv[3],"enabled=1")) return -1;
 if(strncmp(argv[4],"out=",4)) return -1;
 enabled=argv[3][8]=='1';handle=qemu_plugin_request_time_control();if(!handle) return -1;
 out=fopen(argv[4]+4,"wx");if(!out) return -1;fputs("{\"phases\":[",out);
 qemu_plugin_register_vcpu_init_cb(id,init);
 qemu_plugin_register_vcpu_tb_trans_cb(id,translate);
 qemu_plugin_register_atexit_cb(id,finish,NULL);return 0;
}
