/* Experimental bounded request validator; preserves pbuf-chain support. */
#ifndef POC_OS_PBUF_H
#define POC_OS_PBUF_H
#include "lwip/pbuf.h"
static inline int poc_validate_request(const struct pbuf *p, unsigned seed, unsigned expected) {
 unsigned offset=0;
 if(!p || p->tot_len!=expected) return 0;
 for(const struct pbuf *q=p;q;q=q->next) {
  const unsigned char *bytes=q->payload;
  if(q->len>expected-offset) return 0;
  for(unsigned i=0;i<q->len;i++,offset++)
   if(bytes[i]!=(unsigned char)(seed+offset)) return 0;
 }
 return offset==expected;
}
#endif
