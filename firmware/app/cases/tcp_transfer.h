#include "case_api.h"
#include "oracle.h"
#include "stream_io.h"
#include "lwip/init.h"
#include "lwip/netif.h"
#include "lwip/ip4.h"
#include "lwip/tcp.h"
#include "lwip/priv/tcp_priv.h"
#include "lwip/prot/ip4.h"
#include "lwip/inet_chksum.h"
#include <stdio.h>
#include <string.h>
static struct netif interface;
static struct tcp_pcb *connection;
static struct pbuf *pending;
static ip4_addr_t local_ip,peer_ip;
static uint8_t payload[1460] __attribute__((aligned(64)));
static uint8_t packet[1600];
static char output[8192];
static uint32_t peer_sequence=1001,server_sequence;
static unsigned packet_id,phase_id,acked_bytes;
static uint32_t deltas[5];
static const char *kinds[5];
__attribute__((noinline)) void tcp_capture_begin(void) { __asm__ volatile("nop":::"memory"); }
__attribute__((noinline)) void tcp_capture_end(void) { __asm__ volatile("nop":::"memory"); }
static inline uint32_t instret(void) {
 uint32_t v; __asm__ volatile("rdinstret %0":"=r"(v)::"memory");return v;
}
static err_t output_packet(struct netif *netif,struct pbuf *p,const ip4_addr_t *dest) {
 (void)netif;(void)dest;configASSERT(pending==NULL);pbuf_ref(p);pending=p;return ERR_OK;
}
static err_t setup_interface(struct netif *n) {
 n->name[0]='p';n->name[1]='c';n->mtu=1500;n->output=output_packet;return ERR_OK;
}
static err_t on_sent(void *arg,struct tcp_pcb *pcb,u16_t count) {
 (void)arg;(void)pcb;acked_bytes+=count;return ERR_OK;
}
static err_t on_accept(void *arg,struct tcp_pcb *pcb,err_t error) {
 (void)arg;configASSERT(error==ERR_OK);connection=pcb;
 tcp_sent(pcb,on_sent);tcp_nagle_disable(pcb);return ERR_OK;
}
static void inject(uint32_t sequence,uint32_t ack,unsigned flags) {
 unsigned tcp_size=(flags&TCP_SYN)?24:20;
 struct pbuf *p=pbuf_alloc(PBUF_RAW,20+tcp_size,PBUF_RAM);configASSERT(p);
 memset(p->payload,0,p->tot_len);
 struct ip_hdr *ip=p->payload;
 IPH_VHL_SET(ip,4,5);IPH_LEN_SET(ip,lwip_htons(p->tot_len));
 IPH_TTL_SET(ip,64);IPH_PROTO_SET(ip,6);ip->src.addr=peer_ip.addr;ip->dest.addr=local_ip.addr;
 IPH_CHKSUM_SET(ip,inet_chksum(ip,20));
 configASSERT(pbuf_remove_header(p,20)==0);
 struct tcp_hdr *tcp=p->payload;
 tcp->src=lwip_htons(50000);tcp->dest=lwip_htons(1234);
 tcp->seqno=lwip_htonl(sequence);tcp->ackno=lwip_htonl(ack);
 TCPH_HDRLEN_SET(tcp,tcp_size/4);TCPH_FLAGS_SET(tcp,flags);tcp->wnd=lwip_htons(5840);
 if(flags&TCP_SYN) { uint8_t *opt=(uint8_t*)tcp+20;opt[0]=2;opt[1]=4;opt[2]=5;opt[3]=180; }
 tcp->chksum=inet_chksum_pseudo(p,6,p->tot_len,&peer_ip,&local_ip);
 configASSERT(pbuf_add_header(p,20)==0);
 configASSERT(ip4_input(p,&interface)==ERR_OK);
}
static uint32_t consume(unsigned expected_length,uint32_t expected_seq,unsigned flags) {
 configASSERT(pending && pending->tot_len<=sizeof packet);
 unsigned size=pending->tot_len;configASSERT(pbuf_copy_partial(pending,packet,size,0)==size);
 pbuf_free(pending);pending=NULL;
 struct ip_hdr *ip=(void*)packet;
 configASSERT(IPH_HL(ip)==5 && inet_chksum(packet,20)==0);
 struct tcp_hdr *tcp=(void*)(packet+20);
 unsigned header=TCPH_HDRLEN(tcp)*4;
 configASSERT(size==20+header+expected_length && (TCPH_FLAGS(tcp)&flags)==flags);
 configASSERT(expected_seq==UINT32_MAX || lwip_ntohl(tcp->seqno)==expected_seq);
 configASSERT(lwip_ntohl(tcp->ackno)==peer_sequence);
 if(expected_length) configASSERT(memcmp(packet+20+header,payload,expected_length)==0);
 char filename[32];snprintf(filename,sizeof filename,"packet-%u.bin",packet_id++);
 int fd=poc_sh_open(filename);configASSERT(fd>=0);
 configASSERT(poc_write_all(fd,packet,size)==0 && poc_sh_close(fd)==0);
 return lwip_ntohl(tcp->seqno);
}
static void measure(unsigned retry) {
 configASSERT(phase_id<5);
 poc_mark("TCP_TX_BEGIN",phase_id);
 taskENTER_CRITICAL();
 tcp_capture_begin();uint32_t start=instret();
 if(retry) {
  unsigned count=0;
  while(!pending && count++<16) tcp_slowtmr();
  configASSERT(pending);
 } else {
  configASSERT(tcp_write(connection,payload,sizeof payload,POC_TCP_COPY?TCP_WRITE_FLAG_COPY:0)==ERR_OK);
  configASSERT(tcp_output(connection)==ERR_OK);
 }
 deltas[phase_id]=instret()-start;tcp_capture_end();
 taskEXIT_CRITICAL();
 kinds[phase_id]=retry?"retransmit":"send";
 poc_mark("TCP_TX_END",phase_id++);
}
static void transfer_task(void *arg) {
 (void)arg;for(unsigned i=0;i<sizeof payload;i++) payload[i]=(uint8_t)(i*17+31);
 lwip_init();IP4_ADDR(&local_ip,10,0,0,1);IP4_ADDR(&peer_ip,10,0,0,2);
 ip4_addr_t mask,gateway;IP4_ADDR(&mask,255,255,255,0);IP4_ADDR(&gateway,0,0,0,0);
 configASSERT(netif_add(&interface,&local_ip,&mask,&gateway,NULL,setup_interface,ip4_input));
 netif_set_default(&interface);netif_set_up(&interface);netif_set_link_up(&interface);
 struct tcp_pcb *listener=tcp_new();configASSERT(listener);
 configASSERT(tcp_bind(listener,IP_ADDR_ANY,1234)==ERR_OK);
 listener=tcp_listen(listener);configASSERT(listener);tcp_accept(listener,on_accept);
 poc_mark("TCP_HANDSHAKE",0);
 inject(1000,0,TCP_SYN);
 server_sequence=consume(0,UINT32_MAX,TCP_SYN|TCP_ACK)+1;
 inject(peer_sequence,server_sequence,TCP_ACK);
 configASSERT(connection && connection->state==ESTABLISHED && !pending);
 for(unsigned i=0;i<4;i++) {
  measure(0);consume(1460,server_sequence,TCP_ACK);
  if(i==2) { measure(1);consume(1460,server_sequence,TCP_ACK); }
  server_sequence+=1460;inject(peer_sequence,server_sequence,TCP_ACK);
  configASSERT(!pending && acked_bytes==(i+1)*1460);
 }
 configASSERT(phase_id==5 && packet_id==6 && acked_bytes==5840);
 int n=snprintf(output,sizeof output,"{\"case\":\"%s\",\"acked_bytes\":%u,\"retransmits\":1,\"packet_count\":%u,\"phases\":[",POC_CASE,acked_bytes,packet_id);
 for(unsigned i=0;i<phase_id;i++) n+=snprintf(output+n,sizeof(output)-n,"%s{\"phase\":%u,\"kind\":\"%s\",\"instructions\":%u}",i?",":"",i,kinds[i],deltas[i]);
 n+=snprintf(output+n,sizeof(output)-n,"]}\n");configASSERT(n>0&&n<(int)sizeof(output));
 int fd=poc_sh_open("tcp.json");configASSERT(fd>=0&&poc_write_all(fd,output,n)==0&&poc_sh_close(fd)==0);
 poc_sent[poc_sent_count++]=5840;poc_received[poc_received_count++]=acked_bytes;
 poc_oracle_finish();
}
void poc_case_run(void) { configASSERT(xTaskCreate(transfer_task,"tcp_transfer",2048,NULL,2,NULL)==pdPASS); }
