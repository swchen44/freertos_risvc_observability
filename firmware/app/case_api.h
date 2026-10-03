#pragma once
#include "FreeRTOS.h"
#include "task.h"
#include "clock.h"
#include "semihost.h"
void poc_case_run(void);
void poc_mark(const char *phase, unsigned id);
