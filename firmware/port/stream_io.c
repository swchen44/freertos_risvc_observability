#include "stream_io.h"
#include "semihost.h"
int poc_write_all(int fd,const void *data,uint32_t size) {
 const unsigned char *p=data; unsigned retries=0;
 while(size) {
  if(retries++==64) return -1;
  long left=poc_sh_write(fd,p,size);
  if(left<0 || (uint32_t)left>=size) return -1;
  p+=size-(uint32_t)left; size=(uint32_t)left;
 }
 return 0;
}
