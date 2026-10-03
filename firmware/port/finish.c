#include "semihost.h"
void poc_console(const char *s) {
 volatile unsigned char *uart=(volatile unsigned char*)0x10000000UL;
 while(*s) {while(!(uart[5]&0x20)) {} uart[0]=*s++;}
}
void poc_finish(int success) {
 __asm__ volatile("csrci mstatus,8" ::: "memory");
 *(volatile uint32_t*)0x100000UL=success?0x5555:0x13333;
 for(;;) __asm__ volatile("wfi");
}
