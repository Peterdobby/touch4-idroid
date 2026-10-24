/* Exercise the real N1 frame state machine, without MMIO or device access.
 * The two-length prime and success-only NOP commit come from the working
 * Apple N1 driver at 80cb6afc..80cb6b72, not a generated input sequence. */
#include <assert.h>
#include <stdio.h>
typedef unsigned u32;
static long sc(long n,long a,long b,long c,long d,long e,long f)
{(void)n;(void)a;(void)b;(void)c;(void)d;(void)e;(void)f;return 0;}
static void say(const char *s){(void)s;}
static void hex(const char *s,u32 v){(void)s;(void)v;}
static void ms(unsigned n){(void)n;}
static u32 ticks(void){return 0;}
static unsigned sum(const unsigned char *p,unsigned n)
{unsigned v=0;while(n--)v+=*p++;return v;}
static void be16(unsigned char *p,u32 v){p[0]=v>>8;p[1]=v;}
static void mid32(unsigned char *p,u32 v){p[0]=v>>8;p[1]=v;p[2]=v>>24;p[3]=v>>16;}
static int ack(volatile u32 *s,volatile u32 *g){(void)s;(void)g;return 0;}
static u32 reg_read(volatile u32 *s,volatile u32 *g,u32 a)
{(void)s;(void)g;(void)a;return 0;}
static int touch_create(void){return 0;}
static int xfer(volatile u32 *,volatile u32 *,const unsigned char *,unsigned char *,unsigned,unsigned);
#define T4_ACK_DIV 3
#define T4_FW_DIV 5
#define T4_INPUT_HOST_TEST
#define memset t4_memset
#include "../../research/touch-bringup/t4-n1-input01.h"
const unsigned char n81_device_cal[1]={0},n81_device_cal_end[1]={0};
static unsigned emitted;
static int touch_emit(unsigned type,unsigned code,int value)
{(void)type;(void)code;(void)value;emitted++;return 0;}

struct exchange {unsigned phase,nop,length;int fail;unsigned char rx[665];};
static struct exchange queue[16];
static unsigned queued,consumed;
static void put16(unsigned char *p,unsigned n){p[0]=n;p[1]=n>>8;}
static struct exchange *add(unsigned phase,unsigned nop,unsigned length)
{
 struct exchange *e=&queue[queued++];assert(queued<=16);
 t4_memset(e,0,sizeof(*e));e->phase=phase;e->nop=nop;e->length=length;return e;
}
static void length_reply(unsigned nop,unsigned length,unsigned opcode,int bad_checksum)
{
 struct exchange *e=add(0,nop,16);
 e->rx[0]=opcode;put16(e->rx+1,length);packet_sum(e->rx,16);
 if(bad_checksum)e->rx[15]^=1;
}
static void data_reply(unsigned nop,int bad)
{
 struct exchange *e=add(1,nop,59);unsigned char *rx=e->rx;
 rx[0]=0xeb;rx[1]=nop;put16(rx+2,54);rx[4]=(unsigned char)(0-sum(rx,4));
 rx[5]=0x44;rx[7]=24;rx[21]=1;rx[22]=28;
 rx[29]=3;put16(rx+33,1979);put16(rx+35,3348);
 put16(rx+47,260);put16(rx+49,284);put16(rx+57,sum(rx+5,52));
 if(bad==1)rx[0]=0;
 if(bad==2)rx[58]^=1;
 if(bad==3)e->fail=1;
}
static int xfer(volatile u32 *s,volatile u32 *g,const unsigned char *tx,
                unsigned char *rx,unsigned len,unsigned div)
{
 struct exchange *e;unsigned i;
 (void)s;(void)g;assert(div==3 && consumed<queued);e=&queue[consumed++];
 assert(tx[0]==0xeb && tx[1]==e->nop && tx[2]==e->phase && len==e->length);
 if(!e->phase)assert(packet_valid(tx,16));
 else assert(le16(tx+len-2)==0xeb+e->nop+1);
 for(i=0;i<len;i++)rx[i]=e->rx[i];
 return e->fail ? -1 : 0;
}
static void reset(int synced)
{
 queued=consumed=emitted=0;frame_flip=1;frame_command=0xeb;frame_errors=0;
 frame_length_synced=synced;first_frame_reply=0;touch_stop=0;
 touch_width=5000;touch_height=7500;touch_packets=touch_active=0;
}
static void verify(unsigned *nop,int result,unsigned next,int synced)
{
 assert(frame(0,0,nop)==result);assert(*nop==next);
 assert(frame_length_synced==(unsigned)synced && consumed==queued);
}
int main(void)
{
 unsigned nop,bad;
 reset(1);nop=1;length_reply(1,0,0xe1,0);
 verify(&nop,0,2,1); /* Native initial last-success flag is1. */
 length_reply(2,54,0xeb,0);data_reply(2,0);verify(&nop,2,1,1);
 reset(0);nop=1;
 length_reply(1,0,0xe1,0);length_reply(1,54,0xeb,0);data_reply(1,0);
 verify(&nop,2,2,1);assert(touch_packets==1 && touch_active==1 && emitted==11);
 length_reply(2,54,0xeb,0);data_reply(2,0);verify(&nop,2,1,1);
 assert(touch_packets==2);

 reset(0);nop=1;length_reply(1,0,0xe1,0);length_reply(1,0,0xeb,0);
 verify(&nop,0,2,1);assert(!touch_packets && !emitted);

 for(bad=1;bad<=3;bad++){
  reset(1);nop=2;length_reply(2,54,0xeb,0);data_reply(2,bad);
  verify(&nop,-1,2,0);assert(!touch_packets && !emitted);
  length_reply(2,0,0xe1,0);length_reply(2,54,0xeb,0);data_reply(2,0);
  verify(&nop,2,1,1);assert(touch_packets==1);
 }
 reset(1);nop=1;length_reply(1,54,0xeb,1);verify(&nop,-1,1,0);
 length_reply(1,54,0xeb,0);length_reply(1,54,0xeb,0);data_reply(1,0);
 verify(&nop,2,2,1);

 reset(0);nop=1;length_reply(1,54,0xeb,1);verify(&nop,-1,1,0);
 reset(1);nop=1;length_reply(1,54,0,0);verify(&nop,-1,1,0);
 reset(1);nop=1;length_reply(1,661,0xeb,0);verify(&nop,-1,1,0);
 reset(0);nop=1;
 {struct exchange *e=add(0,1,16);e->rx[0]=0xea;e->rx[1]=1;put16(e->rx+2,54);e->rx[4]=(unsigned char)(0-sum(e->rx,4));}
 data_reply(1,0);verify(&nop,2,2,1);assert(touch_packets==1);
 reset(0);nop=1;
 {struct exchange *e=add(0,1,16);e->rx[0]=0xea;e->rx[1]=1;put16(e->rx+2,54);e->rx[4]=(unsigned char)(0-sum(e->rx,4));}
 data_reply(1,2);verify(&nop,-1,1,0);assert(!touch_packets && !emitted);
 puts("N1_FRAME_PIPELINE_PASS: stale control reply, same-NOP prime, success-only commit, error re-prime, bounds");
 return 0;
}
