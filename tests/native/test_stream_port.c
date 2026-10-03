#include <assert.h>
#include <stdint.h>
#include "stream_io.h"
static long replies[10]; static unsigned index_, calls;
long poc_sh_write(int fd, const void *data, uint32_t size) {
    (void)fd; (void)data; (void)size; calls++; return replies[index_++];
}
static void reset(long first, long second) {index_=calls=0; replies[0]=first; replies[1]=second;}
int main(void) {
 char payload[8]={0};
 reset(0,0); assert(poc_write_all(1,payload,8)==0); assert(calls==1);
 reset(3,0); assert(poc_write_all(1,payload,8)==0); assert(calls==2);
 reset(8,0); assert(poc_write_all(1,payload,8)==-1); assert(calls==1);
 reset(-1,0); assert(poc_write_all(1,payload,8)==-1);
 reset(9,0); assert(poc_write_all(1,payload,8)==-1);
 reset(0,0); assert(poc_write_all(1,payload,0)==0); assert(calls==0);
 return 0;
}
