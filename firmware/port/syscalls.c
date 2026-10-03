/* Bounded newlib heap, separate from FreeRTOS heap and startup stack. */
#include <stddef.h>
#include <stdint.h>
#include <errno.h>
static unsigned char arena[8192] __attribute__((aligned(16)));
static ptrdiff_t used;
void *_sbrk(ptrdiff_t increment) {
 if(increment<0 || (size_t)increment>sizeof(arena)-(size_t)used) {errno=ENOMEM;return (void*)-1;}
 void *result=arena+used;used+=increment;return result;
}
