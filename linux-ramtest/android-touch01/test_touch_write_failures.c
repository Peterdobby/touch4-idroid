/* Host-only regression: exercise the real writer with mocked syscalls/logging.
 * Compile this source to a temporary directory; no device access is needed. */
#include <assert.h>
#include <stdio.h>
#include <string.h>

static long sc(long,long,long,long,long,long,long);
static void say(const char *);
static void hex(const char *,unsigned);
#define T4_INPUT_HOST_TEST
#define T4_INPUT_HOST_WRITE_TEST
#include "../../research/touch-bringup/t4-touch-uinput.h"

static struct t4_input_event events[32];
static unsigned attempts,fail_at,log_count;
static long failure_result;
static unsigned logged_result,logged_type,logged_code;

static long sc(long number,long fd,long buffer,long length,long d,long e,long f)
{
 assert(number==4 && fd==7 && length==sizeof(struct t4_input_event));
 assert(d==0 && e==0 && f==0 && attempts<32);
 events[attempts]=*(const struct t4_input_event *)buffer;
 attempts++;
 return attempts==fail_at ? failure_result : length;
}
static void say(const char *message)
{
 assert(strcmp(message,"T4_INPUT EMIT_WRITE_FAILED\n")==0);
 log_count++;
}
static void hex(const char *label,unsigned value)
{
 if(strcmp(label,"T4_INPUT EMIT_WRITE_RESULT")==0)logged_result=value;
 else if(strcmp(label,"T4_INPUT EMIT_EVENT_TYPE")==0)logged_type=value;
 else {assert(strcmp(label,"T4_INPUT EMIT_EVENT_CODE")==0);logged_code=value;}
}
static void reset(unsigned failure_index,long result)
{
 touch_fd=7;touch_width=5000;touch_height=7500;
 touch_packets=7;touch_active=2;touch_stop=0;
 attempts=0;fail_at=failure_index;failure_result=result;log_count=0;
 logged_result=logged_type=logged_code=~0u;
}
static void packet(unsigned char *data,int down)
{
 memset(data,0,52);data[0]=0x44;data[2]=24;
 if(down){
  data[16]=1;data[17]=28;
  data[24]=3;data[28]=0xbb;data[29]=7; /* X=1979 */
  data[30]=0x14;data[31]=13; /* raw Y=3348, screen Y=4152 */
  data[36]=10;data[42]=4;data[43]=1;data[44]=28;data[45]=1;
 }
}
int main(void)
{
 unsigned char data[52];unsigned down,index,total;
 const long failures[]={-4,-5,0,8};unsigned failure;
 for(down=0;down<=1;down++){
  packet(data,down);total=down ? 11 : 4;
  reset(0,0);
  assert(touch_report_packet(data,sizeof(data))==(int)down);
  assert(attempts==total && touch_packets==8 && touch_active==down);
  assert(!touch_stop && !log_count);
  assert(events[total-1].type==0 && events[total-1].code==0);
  if(down){assert(events[3].value==1979 && events[4].value==4152);}
  for(index=1;index<=total;index++)for(failure=0;failure<4;failure++){
   reset(index,failures[failure]);
   assert(touch_report_packet(data,sizeof(data))==-1);
   assert(attempts==index); /* No events after the failing write. */
   assert(touch_packets==7 && touch_active==2 && touch_stop==1);
   assert(log_count==1 && logged_result==(unsigned)failures[failure]);
   assert(logged_type==events[index-1].type && logged_code==events[index-1].code);
  }
 }
 puts("TOUCH_WRITE_FAILURES_PASS: down/release, every event, errors and short writes");
 return 0;
}
