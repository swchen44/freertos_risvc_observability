/* Experiment: endpoint-controlled lwIP algorithm 3; still compiled -Os. */
/*
 * Copyright (c) 2001-2004 Swedish Institute of Computer Science.
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without modification,
 * are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice,
 *    this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 *    this list of conditions and the following disclaimer in the documentation
 *    and/or other materials provided with the distribution.
 * 3. The name of the author may not be used to endorse or promote products
 *    derived from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR IMPLIED
 * WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT
 * SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT
 * OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
 * IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
 * OF SUCH DAMAGE.
 *
 * This file is part of the lwIP TCP/IP stack.
 *
 * Author: Adam Dunkels <adam@sics.se>
 *
 */

#include <stdint.h>
#define FOLD_U32T(x) (((x) & 0xffffU) + ((x) >> 16))
#define SWAP_BYTES_IN_WORD(x) ((((x) & 0xffU) << 8) | (((x) & 0xff00U) >> 8))
uint16_t
poc_endpoint_chksum(const void *dataptr, int len)
{
  const uint8_t *pb = (const uint8_t *)dataptr;
  const uint16_t *ps;
  uint16_t t = 0;
  const uint32_t *pl;
  uint32_t sum = 0, tmp;
  /* starts at odd byte address? */
  int odd = ((uintptr_t)pb & 1);

  if (odd && len > 0) {
    ((uint8_t *)&t)[1] = *pb++;
    len--;
  }

  ps = (const uint16_t *)(const void *)pb;

  if (((uintptr_t)ps & 3) && len > 1) {
    sum += *ps++;
    len -= 2;
  }

  pl = (const uint32_t *)(const void *)ps;

  /* len is nonnegative by the checksum API contract. */
  const uint32_t *end = pl + ((unsigned)len >> 3) * 2;
  len &= 7;
  while (pl != end) {
    tmp = sum + *pl++;          /* ping */
    if (tmp < sum) {
      tmp++;                    /* add back carry */
    }

    sum = tmp + *pl++;          /* pong */
    if (sum < tmp) {
      sum++;                    /* add back carry */
    }


  }

  /* make room in upper bits */
  sum = FOLD_U32T(sum);

  ps = (const uint16_t *)pl;

  /* 16-bit aligned word remaining? */
  while (len > 1) {
    sum += *ps++;
    len -= 2;
  }

  /* dangling tail byte remaining? */
  if (len > 0) {                /* include odd byte */
    ((uint8_t *)&t)[0] = *(const uint8_t *)ps;
  }

  sum += t;                     /* add end bytes */

  /* Fold 32-bit sum to 16 bits
     calling this twice is probably faster than if statements... */
  sum = FOLD_U32T(sum);
  sum = FOLD_U32T(sum);

  if (odd) {
    sum = SWAP_BYTES_IN_WORD(sum);
  }

  return (uint16_t)sum;
}
