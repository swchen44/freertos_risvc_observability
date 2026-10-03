#include "case_api.h"
#include "oracle.h"
#include <stdio.h>
extern void freertos_risc_v_trap_handler(void);
static TraceStringHandle_t channel;
void poc_mark(const char *phase,unsigned id) {
 char format[80];
 snprintf(format,sizeof format,"POC|%s|%s|%%u",POC_CASE,phase);
 configASSERT(xTracePrintF(channel,format,id)==TRC_SUCCESS);
}
int main(void) {
 __asm__ volatile("csrw mtvec,%0" :: "r"(freertos_risc_v_trap_handler));
 configASSERT(xTraceInitialize()==TRC_SUCCESS);
 configASSERT(xTraceEnable(TRC_START)==TRC_SUCCESS);
 configASSERT(xTraceStringRegister("POC",&channel)==TRC_SUCCESS);
 poc_case_run();vTaskStartScheduler();poc_finish(0);
}
void vAssertCalled(const char *file,uint32_t line) {
 char s[160];snprintf(s,sizeof s,"ASSERT %s:%u\n",file,(unsigned)line);poc_console(s);poc_finish(0);
}
void vApplicationMallocFailedHook(void) {poc_console("malloc failed\n");poc_finish(0);}
void vApplicationStackOverflowHook(TaskHandle_t task,char *name) {(void)task;poc_console(name);poc_console(" stack overflow\n");poc_finish(0);}
