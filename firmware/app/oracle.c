#include "case_api.h"
#include "oracle.h"
#include "stream_io.h"
#include <stdio.h>
#include <string.h>
unsigned poc_sent[16],poc_received[16],poc_sent_count,poc_received_count;
uint32_t poc_delta_ticks,poc_delta_mtime;
int poc_irq_restore_ok;
const char *poc_outcome="normal";
typedef struct {const char *name; unsigned id; uint32_t mtime;} Phase;
static Phase phases[128];static unsigned phase_count;
static char output[16384];
void poc_oracle_record(const char *phase,unsigned id) {
 configASSERT(phase_count<128);
 phases[phase_count++]=(Phase){phase,id,(uint32_t)poc_mtime()};
}
void poc_oracle_finish(void) {
 taskENTER_CRITICAL();
 poc_mark("COMPLETE",0);
 configASSERT(xTraceDisable()==TRC_SUCCESS);
 int n=snprintf(output,sizeof output,"{\"case_id\":\"%s\",\"complete\":true,\"outcome\":\"%s\",\"transport_ok\":true,\"mtime_hz\":10000000,\"tick_hz\":1000,\"delta_ticks\":%u,\"delta_mtime\":\"%u\",\"irq_restore_ok\":%s,\"sent_ids\":[",POC_CASE,poc_outcome,poc_delta_ticks,poc_delta_mtime,poc_irq_restore_ok?"true":"false");
 for(unsigned i=0;i<poc_sent_count;i++) n+=snprintf(output+n,sizeof(output)-n,"%s%u",i?",":"",poc_sent[i]);
 n+=snprintf(output+n,sizeof(output)-n,"],\"received_ids\":[");
 for(unsigned i=0;i<poc_received_count;i++) n+=snprintf(output+n,sizeof(output)-n,"%s%u",i?",":"",poc_received[i]);
 n+=snprintf(output+n,sizeof(output)-n,"],\"phases\":[");
 for(unsigned i=0;i<phase_count;i++) n+=snprintf(output+n,sizeof(output)-n,"%s{\"phase\":\"%s\",\"request_id\":%u,\"mtime\":\"%u\"}",i?",":"",phases[i].name,phases[i].id,phases[i].mtime);
 n+=snprintf(output+n,sizeof(output)-n,"],\"requests\":[");
 unsigned count=0;
 for(unsigned i=0;i<phase_count;i++) if(strcmp(phases[i].name,"START")==0) {
  for(unsigned j=i+1;j<phase_count;j++) if(phases[j].id==phases[i].id && strcmp(phases[j].name,"WORKER_END")==0) {
   n+=snprintf(output+n,sizeof(output)-n,"%s{\"request_id\":%u,\"start_mtime\":\"%u\",\"end_mtime\":\"%u\"}",count++?",":"",phases[i].id,phases[i].mtime,phases[j].mtime);break;
  }
 }
 n+=snprintf(output+n,sizeof(output)-n,"]}\n");
 configASSERT(n>0 && n<(int)sizeof(output));
 int fd=poc_sh_open("oracle.json");
 if(fd<0 || poc_write_all(fd,output,n)!=0 || poc_sh_close(fd)!=0) poc_finish(0);
 poc_console("POC complete\n");poc_finish(1);
}
