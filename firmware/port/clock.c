#include "clock.h"
uint64_t poc_mtime(void) {
 volatile uint32_t *lo=(volatile uint32_t *)0x0200bff8u;
 uint32_t a,b,low;
 do { a=lo[1]; low=lo[0]; b=lo[1]; } while(a!=b);
 return ((uint64_t)a<<32)|low;
}
