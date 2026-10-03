#include "case_api.h"
#include "oracle.h"
#include "semphr.h"
static SemaphoreHandle_t lock_a,lock_b;
static TaskHandle_t supervisor,workers[2];
static volatile unsigned held[2],waiting[2],done[2];
static void worker(void *arg) {
 unsigned index=(unsigned)(uintptr_t)arg,id=index+1;
 configASSERT(ulTaskNotifyTake(pdTRUE,100));
 SemaphoreHandle_t first=(POC_ABBA && id==2)?lock_b:lock_a;
 SemaphoreHandle_t second=(POC_ABBA && id==2)?lock_a:lock_b;
 configASSERT(xSemaphoreTake(first,portMAX_DELAY));held[index]=(first==lock_a)?1:2;
 poc_mark(first==lock_a?"HOLD_A":"HOLD_B",id);
 if(POC_ABBA) {xTaskNotifyGive(supervisor);configASSERT(ulTaskNotifyTake(pdTRUE,100));}
 waiting[index]=(second==lock_a)?1:2;poc_mark(second==lock_a?"WAIT_A":"WAIT_B",id);
 configASSERT(xSemaphoreTake(second,portMAX_DELAY));waiting[index]=0;
 poc_mark("SECOND_ACQUIRED",id);
 configASSERT(xSemaphoreGive(second));configASSERT(xSemaphoreGive(first));held[index]=0;
 done[index]=1;poc_mark("WORK_DONE",id);vTaskSuspend(NULL);
}
static void control(void *arg) {
 (void)arg;xTaskNotifyGive(workers[0]);xTaskNotifyGive(workers[1]);
 if(POC_ABBA) {
  configASSERT(ulTaskNotifyTake(pdFALSE,100));configASSERT(ulTaskNotifyTake(pdFALSE,100));
  xTaskNotifyGive(workers[0]);xTaskNotifyGive(workers[1]);
 }
 vTaskDelay(20);
 if(POC_ABBA) {
  configASSERT(held[0]==1 && held[1]==2 && waiting[0]==2 && waiting[1]==1);
  configASSERT(eTaskGetState(workers[0])==eBlocked && eTaskGetState(workers[1])==eBlocked);
  poc_mark("DEADLOCK_CONFIRMED",2);poc_outcome="deadlock";
 } else {configASSERT(done[0] && done[1]);poc_outcome="normal";}
 poc_oracle_finish();
}
void poc_case_run(void) {
 lock_a=xSemaphoreCreateMutex();lock_b=xSemaphoreCreateMutex();configASSERT(lock_a && lock_b);
 vQueueAddToRegistry(lock_a,"lock_A");vQueueAddToRegistry(lock_b,"lock_B");
 configASSERT(xTaskCreate(control,"supervisor",1024,NULL,5,&supervisor)==pdPASS);
 configASSERT(xTaskCreate(worker,"T1",512,(void*)0,3,&workers[0])==pdPASS);
 configASSERT(xTaskCreate(worker,"T2",512,(void*)1,3,&workers[1])==pdPASS);
}
