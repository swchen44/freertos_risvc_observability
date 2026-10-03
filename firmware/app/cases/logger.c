#include "case_api.h"
#include "oracle.h"
static TaskHandle_t coordinator,worker,logger;
static void busy(unsigned ticks) {uint64_t start=poc_mtime();while(poc_mtime()-start<(uint64_t)ticks*10000) {__asm__ volatile("nop");}}
static void work(void *arg) {
 (void)arg;
 for(unsigned i=0;i<8;i++) {
  configASSERT(ulTaskNotifyTake(pdTRUE,100));poc_mark("WORKER_BEGIN",i);
  busy(2);poc_mark("WORKER_END",i);xTaskNotifyGive(coordinator);
 }
 vTaskSuspend(NULL);
}
static void log_task(void *arg) {
 (void)arg;
 for(unsigned i=0;i<8;i++) {
  configASSERT(ulTaskNotifyTake(pdTRUE,100));poc_mark("LOGGER_BEGIN",i);
  busy(8);poc_mark("LOGGER_END",i);xTaskNotifyGive(coordinator);
 }
 vTaskSuspend(NULL);
}
static void control(void *arg) {
 (void)arg;
 for(unsigned i=0;i<8;i++) {
  poc_mark("START",i);xTaskNotifyGive(worker);xTaskNotifyGive(logger);
  configASSERT(ulTaskNotifyTake(pdFALSE,100));
  configASSERT(ulTaskNotifyTake(pdFALSE,100));
 }
 poc_oracle_finish();
}
void poc_case_run(void) {
 poc_outcome=POC_LOGGER_FIXED?"normal":"interference";
 configASSERT(xTaskCreate(control,"coordinator",1024,NULL,5,&coordinator)==pdPASS);
 configASSERT(xTaskCreate(work,"worker",512,NULL,2,&worker)==pdPASS);
 configASSERT(xTaskCreate(log_task,"logger",512,NULL,POC_LOGGER_FIXED?1:4,&logger)==pdPASS);
}
