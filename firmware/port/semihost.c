#include "semihost.h"
#include <string.h>
static long call(long op, uintptr_t *params) {
 register long a0 __asm__("a0")=op;
 register uintptr_t *a1 __asm__("a1")=params;
 __asm__ volatile(".option push\n.option norvc\nslli zero,zero,0x1f\nebreak\nsrai zero,zero,7\n.option pop" : "+r"(a0) : "r"(a1) : "memory");
 return a0;
}
int poc_sh_open(const char *name) {uintptr_t p[]={(uintptr_t)name,5,strlen(name)};return call(1,p);}
int poc_sh_close(int fd) {uintptr_t p[]={(uintptr_t)fd};return call(2,p);}
long poc_sh_write(int fd,const void *data,uint32_t size) {uintptr_t p[]={(uintptr_t)fd,(uintptr_t)data,size};return call(5,p);}
