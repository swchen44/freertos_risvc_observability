/* SPDX-License-Identifier: GPL-2.0-or-later
 * Opt-in RV32 single-core boundary observer. Does not alter guest memory.
 */
#include "live_context.h"
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint64_t begin_pc,end_pc,trap_pc,selected_pc,tcb_address,mrets[16];
static unsigned mret_count,seq,depth,failed,started,ended,pending;
static uint32_t pending_task;
static uint64_t last_index;
static FILE *out;
static struct qemu_plugin_register *mcause;
static int emit(uint64_t index,uint64_t pc,const char *kind,const char *phase,
                int have_task,uint32_t task,int have_cause,uint32_t cause) {
 if(!out || seq>=100000) {failed=1;return -1;}
 char task_text[24]="null",cause_text[24]="null";
 if(have_task) snprintf(task_text,sizeof(task_text),"%"PRIu32,task);
 if(have_cause) snprintf(cause_text,sizeof(cause_text),"%"PRIu32,cause);
 int result=fprintf(out,"{\"schema\":\"context-event-v1\",\"seq\":%u,"
  "\"event_index\":%"PRIu64",\"phase\":\"%s\",\"pc\":%"PRIu64","
  "\"kind\":\"%s\",\"task_id\":%s,\"cause\":%s,\"depth\":%u,"
  "\"evidence\":\"elf-boundary-v1\"}\n",
  seq++,index,phase,pc,kind,task_text,cause_text,depth);
 if(result<0) failed=1;
 last_index=index;
 return result<0?-1:0;
}
static void fault(uint64_t index,uint64_t pc,const char *reason) {
 if(!failed) {
  fprintf(stderr,"context_fault %s\n",reason);
  emit(index,pc,"fault","before",0,0,0,0);
 }
 failed=1;
}
static int task_read(uint64_t index,uint64_t pc,uint32_t *task) {
 GByteArray *bytes=g_byte_array_new();
 int ok=qemu_plugin_read_memory_vaddr(tcb_address,bytes,4) && bytes->len==4;
 uint32_t value=0;
 if(ok) for(unsigned i=0;i<4;i++) value|=(uint32_t)bytes->data[i]<<(8*i);
 g_byte_array_free(bytes,TRUE);
 if(!ok || value<0x80000000 || value>=0x88000000 || value%4) {
  fault(index,pc,"task-memory-read");return -1;
 }
 *task=value;return 0;
}
int context_init(const char *config,const char *output) {
 FILE *in=fopen(config,"r");if(!in)return -1;
 const char *keys[]={"version","xlen","endian","capture_begin_pc","capture_end_pc",
                     "trap_entry_pc","selected_task_pc","current_tcb_address","mret_count"};
 uint64_t values[25]={0};unsigned seen[25]={0};char line[160];int error=0;
 while(fgets(line,sizeof(line),in)) {
  char *equal=strchr(line,'=');if(!equal) {error=1;break;}
  *equal++='\0';int slot=-1;
  for(int k=0;k<9;k++) if(!strcmp(line,keys[k]))slot=k;
  for(int k=0;k<16;k++) {char name[20];snprintf(name,sizeof(name),"mret_%d",k);if(!strcmp(line,name))slot=9+k;}
  if(slot<0 || seen[slot]++) {error=1;break;}
  size_t n=strlen(equal);if(n && equal[n-1]=='\n')equal[--n]='\0';
  if(!n || strspn(equal,"0123456789")!=n) {error=1;break;}
  errno=0;char *tail;values[slot]=strtoull(equal,&tail,10);
  if(errno || *tail || values[slot]>UINT32_MAX) {error=1;break;}
 }
 if(ferror(in))error=1;
 if(fclose(in))error=1;
 for(unsigned k=0;k<9;k++)if(!seen[k])error=1;
 if(values[0]!=1 || values[1]!=32 || values[2]!=1 || !values[8] || values[8]>16)error=1;
 if(error)return -1;
 mret_count=(unsigned)values[8];
 for(unsigned k=0;k<16;k++)if(seen[9+k]!=(k<mret_count))return -1;
 for(unsigned k=3;k<8;k++)if(values[k]<0x80000000 || values[k]>=0x88000000 || values[k]%2)return -1;
 if(values[7]%4 || values[3]==values[4])return -1;
 for(unsigned k=0;k<mret_count;k++) {
  if(values[9+k]<0x80000000 || values[9+k]>=0x88000000 || values[9+k]%2)return -1;
  for(unsigned j=0;j<k;j++)if(values[9+j]==values[9+k])return -1;
  mrets[k]=values[9+k];
 }
 begin_pc=values[3];end_pc=values[4];trap_pc=values[5];selected_pc=values[6];tcb_address=values[7];
 out=fopen(output,"wx");return out?0:-1;
}
void context_vcpu_init(qemu_plugin_id_t id,unsigned cpu) {
 (void)id;
 if(cpu) {fault(0,begin_pc,"multiple-vcpu");return;}
 GArray *regs=qemu_plugin_get_registers();unsigned matches=0;
 for(guint n=0;n<regs->len;n++) {
  qemu_plugin_reg_descriptor r=g_array_index(regs,qemu_plugin_reg_descriptor,n);
  if(!strcmp(r.name,"mcause")) {mcause=r.handle;matches++;}
 }
 fprintf(stderr,"context_capabilities registers=%u mcause_matches=%u\n",regs->len,matches);
 g_array_free(regs,TRUE);
 if(matches!=1)fault(0,begin_pc,"mcause-unavailable");
}
void context_before_instruction(uint64_t index,uint64_t pc) {
 if(failed)return;
 uint32_t task;
 if(pc==begin_pc) {
  if(started || index || task_read(index,pc,&task)) {fault(index,pc,"invalid-begin");return;}
  started=1;emit(index,pc,"begin","before",1,task,0,0);return;
 }
 if(!started || ended) {fault(index,pc,"outside-capture");return;}
 if(pending) {
  if(task_read(index,pc,&task))return;
  if(task!=pending_task) {fault(index,pc,"return-task-changed");return;}
  pending=0;depth=0;emit(index,pc,"return_commit","before",1,task,0,0);
 }
 if(pc==end_pc) {
  if(depth) {fault(index,pc,"open-trap-at-end");return;}
  ended=1;emit(index,pc,"end","before",0,0,0,0);return;
 }
 if(pc==trap_pc) {
  if(depth) {fault(index,pc,"nested-trap-unsupported");return;}
  GByteArray *bytes=g_byte_array_new();
  int n=qemu_plugin_read_register(mcause,bytes);uint32_t cause=0;
  int valid=n==4 && bytes->len==4;
  if(valid)for(unsigned i=0;i<4;i++)cause|=(uint32_t)bytes->data[i]<<(8*i);
  g_byte_array_free(bytes,TRUE);
  if(!valid) {fault(index,pc,"mcause-read");return;}
  depth=1;emit(index,pc,"trap_enter","before",0,0,1,cause);
 }
 if(pc==selected_pc) {
  if(!depth || task_read(index,pc,&task)) {fault(index,pc,"selection-outside-trap");return;}
  emit(index,pc,"selected_task","before",1,task,0,0);
 }
}
int context_needs_registers(uint64_t pc) {return pc==trap_pc;}
void context_after_instruction(uint64_t index,uint64_t pc) {
 if(failed)return;
 for(unsigned n=0;n<mret_count;n++)if(pc==mrets[n]) {
  if(!depth || pending || task_read(index,pc,&pending_task)) {fault(index,pc,"invalid-mret");return;}
  pending=1;emit(index,pc,"mret_pending","after",1,pending_task,0,0);
 }
}
int context_finish(uint64_t raw_events) {
 if(!started || !ended || depth || pending || last_index!=raw_events)failed=1;
 if(out && fclose(out))failed=1;
 out=NULL;
 return failed?1:0;
}
