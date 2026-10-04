/* SPDX-License-Identifier: GPL-2.0-or-later
 * QEMU 9.2/API4 boundary probe. Guest mtime anchors absolute targets after WFI.
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
static uint64_t trigger;
static unsigned enabled,count,idle_count,resume_count,wfi_count;
static uint64_t insns,wfi_start,wfi_span;
static struct qemu_plugin_register *regs[4];
static GByteArray *bytes;
static const void *handle;
static FILE *out;
static const unsigned delays[5]={1000000,2000000,0,3000000,1000000};
static void fail(const char *msg) {fprintf(stderr,"clock_edges: %s\n",msg);exit(2);}
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
 if(cpu) fail("extra vCPU");
 insns++;
 if((uintptr_t)data) {wfi_count++;wfi_start=insns;}
}
static void execute(unsigned cpu,void *data) {
 (void)data;if(cpu) fail("extra vCPU");
 uint64_t anchor=reg(0)|((uint64_t)reg(1)<<32);
 unsigned delay=reg(2),id=reg(3);
 if(count>=5||id!=count||delay!=delays[id]) fail("request sequence");
 uint64_t target=id==2?0:anchor+delay;
 if(id==4) wfi_span=insns-wfi_start;
 if(target>INT64_MAX) fail("target overflow");
 char target_text[32];const char *mode="absolute_target";
 snprintf(target_text,sizeof target_text,"%"PRIu64,target);
#ifdef POC_RELATIVE
 if(id!=2) {strcpy(target_text,"null");mode="relative_cost";}
#endif
 if(fprintf(out,"%s{\"id\":%u,\"delay_ns\":%u,\"anchor_ns\":%"PRIu64",\"target_ns\":%s,\"anchor_target_ns\":%"PRIu64",\"mode\":\"%s\",\"applied\":%s,\"wfi_before\":%u}",count?",":"",id,delay,anchor,target_text,target,mode,enabled?"true":"false",wfi_count)<0) fail("receipt write");
 fflush(out);count++;
 if(enabled) {
#ifdef POC_RELATIVE
  if(id==2) qemu_plugin_update_ns(handle,0);
  else qemu_plugin_poc_add_ns(handle,delay);
#else
  qemu_plugin_update_ns(handle,(int64_t)target);
#endif
 }
}
static void translate(qemu_plugin_id_t id,struct qemu_plugin_tb *tb) {
 (void)id;
 for(size_t n=0;n<qemu_plugin_tb_n_insns(tb);n++) {
  struct qemu_plugin_insn *i=qemu_plugin_tb_get_insn(tb,n);
  uint32_t opcode=0;
  size_t size=qemu_plugin_insn_data(i,&opcode,4);
  int is_wfi=size==4&&GUINT32_FROM_LE(opcode)==0x10500073;
  qemu_plugin_register_vcpu_insn_exec_cb(i,count_instruction,QEMU_PLUGIN_CB_NO_REGS,
                                        (void*)(uintptr_t)is_wfi);
  if(qemu_plugin_insn_vaddr(i)==trigger)
   qemu_plugin_register_vcpu_insn_exec_cb(i,execute,QEMU_PLUGIN_CB_R_REGS,NULL);
 }
}
static void idle(qemu_plugin_id_t id,unsigned cpu) {(void)id;(void)cpu;idle_count++;}
static void resume(qemu_plugin_id_t id,unsigned cpu) {(void)id;(void)cpu;resume_count++;}
static void finish(qemu_plugin_id_t id,void *data) {
 (void)id;(void)data;
 if(count!=5) fail("incomplete requests");
 if(fprintf(out,"],\"idle\":%u,\"resume\":%u,\"wfi_count\":%u,\"wfi_span_insns\":%"PRIu64"}\n",idle_count,resume_count,wfi_count,wfi_span)<0||fclose(out)) fail("receipt close");
 g_byte_array_free(bytes,TRUE);
}
QEMU_PLUGIN_EXPORT int qemu_plugin_install(qemu_plugin_id_t id,const qemu_info_t *info,int argc,char **argv) {
 if(!info->system_emulation||info->system.smp_vcpus!=1||argc!=3) return -1;
 if(strncmp(argv[0],"trigger=",8)||strncmp(argv[1],"enabled=",8)||strncmp(argv[2],"out=",4)) return -1;
 char *end;errno=0;trigger=strtoull(argv[0]+8,&end,16);
 if(errno||*end||!trigger) return -1;
 if(strcmp(argv[1]+8,"0")&&strcmp(argv[1]+8,"1")) return -1;
 enabled=argv[1][8]=='1';handle=qemu_plugin_request_time_control();if(!handle) return -1;
 out=fopen(argv[2]+4,"wx");if(!out) return -1;fputs("{\"requests\":[",out);
 qemu_plugin_register_vcpu_init_cb(id,init);
 qemu_plugin_register_vcpu_idle_cb(id,idle);
 qemu_plugin_register_vcpu_resume_cb(id,resume);
 qemu_plugin_register_vcpu_tb_trans_cb(id,translate);
 qemu_plugin_register_atexit_cb(id,finish,NULL);return 0;
}
