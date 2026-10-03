#include "case_api.h"
#include "oracle.h"
#include "semphr.h"
static SemaphoreHandle_t lock;
static TaskHandle_t coordinator,low,medium,high;
static void busy(unsigned ticks) {uint64_t start=poc_mtime();while(poc_mtime()-start<(uint64_t)ticks*10000) {__asm__ volatile("nop");}}
static void low_task(void *arg) {
 (void)arg;configASSERT(ulTaskNotifyTake(pdTRUE,100));
 configASSERT(xSemaphoreTake(lock,100));poc_mark("LOW_HOLD",0);xTaskNotifyGive(coordinator);
 configASSERT(ulTaskNotifyTake(pdTRUE,100));poc_mark("LOW_RESUME",uxTaskPriorityGet(NULL));
 busy(2);poc_mark("LOW_RELEASE",0);configASSERT(xSemaphoreGive(lock));
 configASSERT(uxTaskPriorityGet(NULL)==2);poc_mark("LOW_RESTORED",2);xTaskNotifyGive(coordinator);vTaskSuspend(NULL);
}
static void medium_task(void *arg) {
 (void)arg;configASSERT(ulTaskNotifyTake(pdTRUE,100));poc_mark("MEDIUM_BEGIN",0);
 busy(6);poc_mark("MEDIUM_END",0);xTaskNotifyGive(coordinator);vTaskSuspend(NULL);
}
static void high_task(void *arg) {
 (void)arg;configASSERT(ulTaskNotifyTake(pdTRUE,100));poc_mark("HIGH_ATTEMPT",0);xTaskNotifyGive(coordinator);
 configASSERT(xSemaphoreTake(lock,100));poc_mark("HIGH_ACQUIRED",0);configASSERT(xSemaphoreGive(lock));
 xTaskNotifyGive(coordinator);vTaskSuspend(NULL);
}
static void control(void *arg) {
 (void)arg;xTaskNotifyGive(low);configASSERT(ulTaskNotifyTake(pdFALSE,100));
 xTaskNotifyGive(high);configASSERT(ulTaskNotifyTake(pdFALSE,100));
 unsigned attempts=0;
 do {vTaskDelay(1);attempts++;} while(eTaskGetState(high)!=eBlocked && attempts<5);
 configASSERT(eTaskGetState(high)==eBlocked);poc_mark("HIGH_BLOCKED",0);
 xTaskNotifyGive(medium);xTaskNotifyGive(low);
 for(unsigned i=0;i<3;i++) configASSERT(ulTaskNotifyTake(pdFALSE,100));
 poc_oracle_finish();
}
void poc_case_run(void) {
 poc_outcome=POC_USE_MUTEX?"normal":"priority_inversion";
 lock=POC_USE_MUTEX?xSemaphoreCreateMutex():xSemaphoreCreateBinary();configASSERT(lock);
 if(!POC_USE_MUTEX) configASSERT(xSemaphoreGive(lock));
 vQueueAddToRegistry(lock,POC_USE_MUTEX?"resource_mutex":"resource_binary");
 configASSERT(xTaskCreate(control,"coordinator",1024,NULL,5,&coordinator)==pdPASS);
 configASSERT(xTaskCreate(low_task,"low",512,NULL,2,&low)==pdPASS);
 configASSERT(xTaskCreate(medium_task,"medium",512,NULL,3,&medium)==pdPASS);
 configASSERT(xTaskCreate(high_task,"high",512,NULL,4,&high)==pdPASS);
}
