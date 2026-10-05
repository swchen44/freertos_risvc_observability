/* Z0: bounded raw-API request/response, continuous trace, no file I/O in capture. */
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
#include "lwip/stats.h"
#ifdef POC_PBUF_WALK
#include "os_pbuf.h"
#endif
#include <stdio.h>
#include <string.h>

static struct netif interface;
static struct tcp_pcb *connection;
static struct pbuf *pending;
static ip4_addr_t local_ip, peer_ip;
static uint8_t payload[1460] __attribute__((aligned(64)));
static uint8_t request[64];
static uint8_t packets[32][1600] __attribute__((aligned(4)));
static unsigned lengths[32], directions[32], packet_count;
static unsigned received, acked, retained, peak_retained, round_id, peer_closed;
static unsigned resources_before[6], resources_after[6];
static uint32_t client_seq=1001, server_seq;
typedef struct { const char *kind; unsigned round; uint32_t instructions; } Phase;
static Phase phases[40];
static unsigned phase_count;
static char output[16384];
#ifdef POC_FRAGMENTED_REQUEST
static unsigned request_lengths[2][3], request_totals[2][3];
#endif
#ifdef POC_LIVE_TIMING
static uint32_t timing_before,timing_after,timing_ticks;
#ifdef POC_LIVE_IRQ
static volatile unsigned observer_woke,observer_tick,observer_mtime;
static unsigned timing_start_tick,timing_woke,timing_observer_tick,timing_observer_mtime;
static void timing_observer(void *arg) {
 (void)arg;vTaskDelay(2);
 observer_tick=xTaskGetTickCount();observer_mtime=(uint32_t)poc_mtime();observer_woke=1;
 poc_mark("TCP_IRQ_OBSERVER",observer_tick);vTaskSuspend(NULL);
}
#endif
#endif

__attribute__((noinline)) void tcp_capture_begin(void) { __asm__ volatile("nop":::"memory"); }
__attribute__((noinline)) void tcp_capture_end(void) { __asm__ volatile("nop":::"memory"); }
__attribute__((noinline)) void z0_stack_begin(void) { __asm__ volatile("nop":::"memory"); }
__attribute__((noinline)) void z0_stack_end(void) { __asm__ volatile("nop":::"memory"); }
static inline uint32_t instret(void) {
 uint32_t v; __asm__ volatile("rdinstret %0":"=r"(v)::"memory"); return v;
}
static uint32_t phase_start(void) { z0_stack_begin();return instret(); }
static void phase(const char *name, uint32_t start) {
 uint32_t delta=instret()-start;
 z0_stack_end();
 configASSERT(phase_count<40);
 phases[phase_count++]=(Phase){name,round_id,delta};
}
static void snapshot(struct pbuf *p, unsigned rx) {
 configASSERT(packet_count<32 && p->tot_len<=1600);
 lengths[packet_count]=p->tot_len; directions[packet_count]=rx;
 configASSERT(pbuf_copy_partial(p,packets[packet_count],p->tot_len,0)==p->tot_len);
 packet_count++;
}
static err_t output_packet(struct netif *n,struct pbuf *p,const ip4_addr_t *dest) {
 (void)n;(void)dest; configASSERT(!pending); pbuf_ref(p); pending=p; return ERR_OK;
}
static err_t setup(struct netif *n) {
 n->name[0]='z';n->name[1]='0';n->mtu=1500;n->output=output_packet;return ERR_OK;
}
static err_t on_sent(void *arg,struct tcp_pcb *pcb,u16_t len) {
 (void)arg;(void)pcb;configASSERT(len<=retained);retained-=len;acked+=len;return ERR_OK;
}
static err_t on_recv(void *arg,struct tcp_pcb *pcb,struct pbuf *p,err_t err) {
 (void)arg; configASSERT(err==ERR_OK);
 if(!p) { peer_closed=1;return ERR_OK; }
 configASSERT(p->tot_len==64);
#ifdef POC_FRAGMENTED_REQUEST
 unsigned nodes=0;
 configASSERT(round_id<2);
 for(const struct pbuf *q=p;q;q=q->next) {
  configASSERT(nodes<3);
  request_lengths[round_id][nodes]=q->len;
  request_totals[round_id][nodes]=q->tot_len;
  nodes++;
 }
 configASSERT(nodes==3);
#endif
#ifdef POC_PBUF_WALK
 configASSERT(poc_validate_request(p,round_id,64));
#else
 for(unsigned i=0;i<64;i++) configASSERT(pbuf_get_at(p,i)==(uint8_t)(round_id+i));
#endif
 received+=p->tot_len;tcp_recved(pcb,p->tot_len);pbuf_free(p);return ERR_OK;
}
static err_t on_accept(void *arg,struct tcp_pcb *pcb,err_t err) {
 (void)arg;configASSERT(err==ERR_OK);connection=pcb;
 tcp_sent(pcb,on_sent);tcp_recv(pcb,on_recv);tcp_nagle_disable(pcb);return ERR_OK;
}
static void resources(unsigned *out) {
 out[0]=lwip_stats.mem.used;
 out[1]=lwip_stats.memp[MEMP_TCP_PCB]->used;
 out[2]=lwip_stats.memp[MEMP_TCP_PCB_LISTEN]->used;
 out[3]=lwip_stats.memp[MEMP_TCP_SEG]->used;
 out[4]=lwip_stats.memp[MEMP_PBUF]->used;
 out[5]=lwip_stats.memp[MEMP_PBUF_POOL]->used;
}
#ifdef POC_FRAGMENTED_REQUEST
/* One IP packet, three memory buffers; first buffer retains both protocol headers. */
static struct pbuf *fragment_request(struct pbuf *packet) {
 configASSERT(packet->tot_len==104);
 struct pbuf *head=pbuf_alloc(PBUF_RAW,53,PBUF_RAM);
 struct pbuf *empty=pbuf_alloc(PBUF_RAW,0,PBUF_RAM);
 struct pbuf *tail=pbuf_alloc(PBUF_RAW,51,PBUF_RAM);
 configASSERT(head&&empty&&tail);
 configASSERT(pbuf_copy_partial(packet,head->payload,53,0)==53);
 configASSERT(pbuf_copy_partial(packet,tail->payload,51,53)==51);
 pbuf_cat(head,empty);pbuf_cat(head,tail);
 configASSERT(head->tot_len==104&&head->len==53&&empty->len==0&&tail->len==51);
 pbuf_free(packet);return head;
}
#endif
/* Peer construction + snapshot happen outside the stack instruction window. */
static void inject(uint32_t seq,uint32_t ack,unsigned flags,const uint8_t *data,unsigned length,const char *kind) {
 unsigned header=(flags&TCP_SYN)?24:20;
 struct pbuf *p=pbuf_alloc(PBUF_RAW,20+header+length,PBUF_RAM);configASSERT(p);
 memset(p->payload,0,p->tot_len);
 struct ip_hdr *ip=p->payload;
 IPH_VHL_SET(ip,4,5);IPH_LEN_SET(ip,lwip_htons(p->tot_len));
 IPH_TTL_SET(ip,64);IPH_PROTO_SET(ip,6);ip->src.addr=peer_ip.addr;ip->dest.addr=local_ip.addr;
 IPH_CHKSUM_SET(ip,inet_chksum(ip,20));configASSERT(pbuf_remove_header(p,20)==0);
 struct tcp_hdr *tcp=p->payload;
 tcp->src=lwip_htons(50000);tcp->dest=lwip_htons(1234);
 tcp->seqno=lwip_htonl(seq);tcp->ackno=lwip_htonl(ack);
 TCPH_HDRLEN_SET(tcp,header/4);TCPH_FLAGS_SET(tcp,flags);tcp->wnd=lwip_htons(5840);
 if(flags&TCP_SYN) {uint8_t *o=(uint8_t*)tcp+20;o[0]=2;o[1]=4;o[2]=5;o[3]=180;}
 if(length) memcpy((uint8_t*)tcp+header,data,length);
 tcp->chksum=inet_chksum_pseudo(p,6,p->tot_len,&peer_ip,&local_ip);
 configASSERT(pbuf_add_header(p,20)==0);
#ifdef POC_FRAGMENTED_REQUEST
 if(length) {configASSERT(length==64);p=fragment_request(p);}
#endif
 snapshot(p,1);
 uint32_t start=phase_start();configASSERT(ip4_input(p,&interface)==ERR_OK);phase(kind,start);
}
static uint32_t consume(unsigned size,uint32_t expected,unsigned flags) {
 configASSERT(pending);snapshot(pending,0);pbuf_free(pending);pending=NULL;
 struct ip_hdr *ip=(void*)packets[packet_count-1];
 struct tcp_hdr *tcp=(void*)((uint8_t*)ip+20);
 configASSERT(lengths[packet_count-1]==20+TCPH_HDRLEN(tcp)*4+size);
 configASSERT((TCPH_FLAGS(tcp)&0x17)==flags);
 configASSERT(lwip_ntohl(tcp->ackno)==client_seq);
 configASSERT(expected==UINT32_MAX || lwip_ntohl(tcp->seqno)==expected);
 if(size) configASSERT(memcmp((uint8_t*)tcp+TCPH_HDRLEN(tcp)*4,payload,size)==0);
 return lwip_ntohl(tcp->seqno);
}
static void save(void) {
 int n=snprintf(output,sizeof output,"{\"case\":\"tcp_request_response\",\"request_bytes\":%u,\"acked_bytes\":%u,\"retained_bytes\":%u,\"peak_retained_bytes\":%u,\"peer_closed\":%s,\"active_pcbs\":0,\"timewait_pcbs\":0,\"resources_before\":[",received,acked,retained,peak_retained,peer_closed?"true":"false");
 for(unsigned i=0;i<6;i++) n+=snprintf(output+n,sizeof(output)-n,"%s%u",i?",":"",resources_before[i]);
 n+=snprintf(output+n,sizeof(output)-n,"],\"resources_after\":[");
 for(unsigned i=0;i<6;i++) n+=snprintf(output+n,sizeof(output)-n,"%s%u",i?",":"",resources_after[i]);
 n+=snprintf(output+n,sizeof(output)-n,"],\"phases\":[");
 for(unsigned i=0;i<phase_count;i++) n+=snprintf(output+n,sizeof(output)-n,"%s{\"kind\":\"%s\",\"round\":%u,\"instructions\":%u}",i?",":"",phases[i].kind,phases[i].round,phases[i].instructions);
 n+=snprintf(output+n,sizeof(output)-n,"],\"packets\":[");
 for(unsigned i=0;i<packet_count;i++) {
  char name[32];snprintf(name,sizeof name,"packet-%u.bin",i);
  int fd=poc_sh_open(name);configASSERT(fd>=0&&poc_write_all(fd,packets[i],lengths[i])==0&&poc_sh_close(fd)==0);
  n+=snprintf(output+n,sizeof(output)-n,"%s{\"file\":\"%s\",\"direction\":\"%s\"}",i?",":"",name,directions[i]?"rx":"tx");
 }
#ifdef POC_FRAGMENTED_REQUEST
 n+=snprintf(output+n,sizeof(output)-n,"]");
 n+=snprintf(output+n,sizeof(output)-n,",\"request_pbufs\":[");
 for(unsigned i=0;i<2;i++) n+=snprintf(output+n,sizeof(output)-n,
  "%s{\"lengths\":[%u,%u,%u],\"totals\":[%u,%u,%u]}",i?",":"",
  request_lengths[i][0],request_lengths[i][1],request_lengths[i][2],
  request_totals[i][0],request_totals[i][1],request_totals[i][2]);
 n+=snprintf(output+n,sizeof(output)-n,"]}\n");
#else
 n+=snprintf(output+n,sizeof(output)-n,"]}\n");
#endif
 configASSERT(n>0&&n<(int)sizeof(output));
 int fd=poc_sh_open("session.json");configASSERT(fd>=0&&poc_write_all(fd,output,n)==0&&poc_sh_close(fd)==0);
}
static void session_task(void *arg) {
 (void)arg;lwip_init();IP4_ADDR(&local_ip,10,0,0,1);IP4_ADDR(&peer_ip,10,0,0,2);
 ip4_addr_t mask,gateway;IP4_ADDR(&mask,255,255,255,0);IP4_ADDR(&gateway,0,0,0,0);
 configASSERT(netif_add(&interface,&local_ip,&mask,&gateway,NULL,setup,ip4_input));
 netif_set_default(&interface);netif_set_up(&interface);netif_set_link_up(&interface);
 resources(resources_before);
 poc_mark("TCP_SESSION_BEGIN",0);
#ifdef POC_LIVE_IRQ
 uint32_t timing_mask=poc_irq_save();
#else
 taskENTER_CRITICAL();
#endif
#ifdef POC_LIVE_TIMING
 timing_ticks=xTaskGetTickCount();timing_before=(uint32_t)poc_mtime();
#endif
 tcp_capture_begin();
#ifdef POC_LIVE_IRQ
 timing_start_tick=timing_ticks;poc_irq_restore(timing_mask);
#endif
 uint32_t start=phase_start();struct tcp_pcb *listener=tcp_new();configASSERT(listener);
 configASSERT(tcp_bind(listener,IP_ADDR_ANY,1234)==ERR_OK);
 listener=tcp_listen(listener);configASSERT(listener);tcp_accept(listener,on_accept);phase("listen",start);
 inject(1000,0,TCP_SYN,NULL,0,"syn");server_seq=consume(0,UINT32_MAX,TCP_SYN|TCP_ACK)+1;
 inject(client_seq,server_seq,TCP_ACK,NULL,0,"establish");
 configASSERT(connection&&connection->state==ESTABLISHED&&!pending);
 for(round_id=0;round_id<2;round_id++) {
  for(unsigned i=0;i<64;i++) request[i]=(uint8_t)(round_id+i);
  inject(client_seq,server_seq,TCP_ACK|TCP_PSH,request,64,"request_rx");client_seq+=64;
  configASSERT(received==(round_id+1)*64&&!pending);
  for(unsigned chunk=0;chunk<4;chunk++) {
   configASSERT(retained==0);
   for(unsigned i=0;i<1460;i++) payload[i]=(uint8_t)(i*17+round_id+chunk);
   start=phase_start();retained=1460;peak_retained=1460;
   configASSERT(tcp_write(connection,payload,1460,0)==ERR_OK);
   configASSERT(tcp_output(connection)==ERR_OK);phase("response_tx",start);
   consume(1460,server_seq,TCP_ACK);server_seq+=1460;
   inject(client_seq,server_seq,TCP_ACK,NULL,0,"response_ack");
   configASSERT(!pending&&retained==0&&acked==(round_id*4+chunk+1)*1460);
  }
  start=phase_start();tcp_fasttmr();tcp_slowtmr();phase("timer_idle",start);configASSERT(!pending);
 }
 client_seq++;inject(client_seq-1,server_seq,TCP_FIN|TCP_ACK,NULL,0,"peer_fin");
 configASSERT(peer_closed&&connection->state==CLOSE_WAIT);consume(0,server_seq,TCP_ACK);
 start=phase_start();configASSERT(tcp_close(connection)==ERR_OK);connection=NULL;phase("close",start);
 consume(0,server_seq,TCP_FIN|TCP_ACK);server_seq++;
 inject(client_seq,server_seq,TCP_ACK,NULL,0,"final_ack");
 start=phase_start();configASSERT(tcp_close(listener)==ERR_OK);phase("listener_close",start);
 configASSERT(!pending&&!tcp_active_pcbs&&!tcp_tw_pcbs&&!tcp_listen_pcbs.pcbs&&!tcp_bound_pcbs);
 resources(resources_after);
 for(unsigned i=0;i<6;i++) configASSERT(resources_before[i]==resources_after[i]);
#ifdef POC_LIVE_IRQ
 timing_mask=poc_irq_save();
#endif
 tcp_capture_end();
#ifdef POC_LIVE_TIMING
 for(volatile unsigned k=0;k<32;k++) __asm__ volatile("nop":::"memory");
 timing_after=(uint32_t)poc_mtime();timing_ticks=xTaskGetTickCount()-timing_ticks;
#endif
#ifdef POC_LIVE_IRQ
 timing_woke=observer_woke;timing_observer_tick=observer_tick;timing_observer_mtime=observer_mtime;
 poc_irq_restore(timing_mask);
#else
 taskEXIT_CRITICAL();
#endif
 poc_mark("TCP_SESSION_END",0);
#ifdef POC_LIVE_TIMING
#ifdef POC_LIVE_IRQ
 int n=snprintf(output,sizeof output,
  "{\"case\":\"tcp_request_response\",\"before\":%u,\"after\":%u,\"before_tick\":%u,\"ticks\":%u,\"work\":%u,\"woke\":%u,\"observer_tick\":%u,\"observer_mtime\":%u}\n",
  timing_before,timing_after,timing_start_tick,timing_ticks,acked,timing_woke,timing_observer_tick,timing_observer_mtime);
#else
 int n=snprintf(output,sizeof output,
  "{\"case\":\"tcp_request_response\",\"before\":%u,\"after\":%u,\"ticks\":%u,\"work\":%u}\n",
  timing_before,timing_after,timing_ticks,acked);
#endif
 configASSERT(n>0&&n<(int)sizeof output);
 int fd=poc_sh_open("live-cache.json");
 configASSERT(fd>=0&&poc_write_all(fd,output,n)==0&&poc_sh_close(fd)==0);
#endif
 save();poc_sent[poc_sent_count++]=11680;poc_received[poc_received_count++]=acked;poc_oracle_finish();
}
void poc_case_run(void) {
#ifdef POC_LIVE_IRQ
 configASSERT(xTaskCreate(timing_observer,"tcp_observer",1024,NULL,3,NULL)==pdPASS);
#endif
 configASSERT(xTaskCreate(session_task,"tcp_session",2048,NULL,2,NULL)==pdPASS);
}
