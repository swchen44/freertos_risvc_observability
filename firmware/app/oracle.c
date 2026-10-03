#include "case_api.h"
#include "oracle.h"
#include "stream_io.h"
#include <stdio.h>
#include <string.h>
unsigned poc_sent[16],poc_received[16],poc_sent_count,poc_received_count;
uint32_t poc_delta_ticks,poc_delta_mtime;
int poc_irq_restore_ok;
static char output[4096];
void poc_oracle_finish(void) {
 taskENTER_CRITICAL();
 poc_mark("COMPLETE",0);
 configASSERT(xTraceDisable()==TRC_SUCCESS);
 int n=snprintf(output,sizeof output,"{\"case_id\":\"%s\",\"complete\":true,\"outcome\":\"normal\",\"transport_ok\":true,\"mtime_hz\":10000000,\"tick_hz\":1000,\"phases\":[],\"requests\":[],\"delta_ticks\":%u,\"delta_mtime\":\"%u\",\"irq_restore_ok\":%s,\"sent_ids\":[",POC_CASE,poc_delta_ticks,poc_delta_mtime,poc_irq_restore_ok?"true":"false");
 for(unsigned i=0;i<poc_sent_count;i++) n+=snprintf(output+n,sizeof(output)-n,"%s%u",i?",":"",poc_sent[i]);
 n+=snprintf(output+n,sizeof(output)-n,"],\"received_ids\":[");
 for(unsigned i=0;i<poc_received_count;i++) n+=snprintf(output+n,sizeof(output)-n,"%s%u",i?",":"",poc_received[i]);
 n+=snprintf(output+n,sizeof(output)-n,"]}\n");
 configASSERT(n>0 && n<(int)sizeof(output));
 int fd=poc_sh_open("oracle.json");
 if(fd<0 || poc_write_all(fd,output,n)!=0 || poc_sh_close(fd)!=0) poc_finish(0);
 poc_console("POC complete\n");poc_finish(1);
}
