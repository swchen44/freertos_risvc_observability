/* Checksum-only port: standard types, little-endian RV32 and host. */
#ifndef POC_LWIP_CC_H
#define POC_LWIP_CC_H
#define LWIP_NOASSERT 1
#ifdef POC_ENDPOINT_CHECKSUM
#include <stdint.h>
uint16_t poc_endpoint_chksum(const void *data, int len);
#define LWIP_CHKSUM poc_endpoint_chksum
#endif
#endif
