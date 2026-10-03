#ifndef FREERTOS_CONFIG_H
#define FREERTOS_CONFIG_H
#include <stdint.h>
#define configMTIME_BASE_ADDRESS 0x0200bff8UL
#define configMTIMECMP_BASE_ADDRESS 0x02004000UL
#define configISR_STACK_SIZE_WORDS 512
#define configUSE_PREEMPTION 1
#define configUSE_IDLE_HOOK 0
#define configUSE_TICK_HOOK 0
#define configCPU_CLOCK_HZ 10000000UL
#define configTICK_RATE_HZ 1000
#define configMINIMAL_STACK_SIZE 256
#define configTOTAL_HEAP_SIZE (128 * 1024)
#define configMAX_TASK_NAME_LEN 20
#define configUSE_TRACE_FACILITY 1
#define configUSE_16_BIT_TICKS 0
#define configIDLE_SHOULD_YIELD 0
#define configUSE_MUTEXES 1
#define configUSE_RECURSIVE_MUTEXES 0
#define configCHECK_FOR_STACK_OVERFLOW 2
#define configUSE_MALLOC_FAILED_HOOK 1
#define configUSE_COUNTING_SEMAPHORES 1
#define configMAX_PRIORITIES 8
#define configQUEUE_REGISTRY_SIZE 16
#define configSUPPORT_STATIC_ALLOCATION 0
#define configUSE_TIMERS 0
#define configUSE_TASK_NOTIFICATIONS 1
#define INCLUDE_vTaskPrioritySet 1
#define INCLUDE_uxTaskPriorityGet 1
#define INCLUDE_vTaskDelete 1
#define INCLUDE_vTaskSuspend 1
#define INCLUDE_vTaskDelayUntil 1
#define INCLUDE_vTaskDelay 1
#define INCLUDE_xTaskGetSchedulerState 1
#define INCLUDE_xTaskGetIdleTaskHandle 1
#define INCLUDE_xTaskGetCurrentTaskHandle 1
#define INCLUDE_eTaskGetState 1
#define INCLUDE_xSemaphoreGetMutexHolder 1
void vAssertCalled(const char *, uint32_t);
#define configASSERT(x) do { if (!(x)) vAssertCalled(__FILE__, __LINE__); } while (0)
#include "trcRecorder.h"
#endif
