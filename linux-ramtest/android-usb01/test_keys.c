/* Exercises the exact state machine included in the native kernel driver. */
#include "t4-keys-state.h"
static struct t4_keys_state s;
static unsigned n, actions[256], values[256];
static void emit(void *ctx,unsigned action,int value)
{
    (void)ctx;
    if(n<256) { actions[n]=action;values[n]=value; }
    n++;
}
static void seed(unsigned mask) { n=0;t4_keys_seed(&s,mask); }
static void poll(unsigned mask,unsigned count)
{
    while(count--) t4_keys_step(&s,mask,emit,0);
}
#define CHECK(x) do { if(!(x)) return __LINE__; } while(0)
int main(void)
{
    unsigned i;
    seed(0);poll(0,200);CHECK(n==0);
    /* Contact bounce never creates a press or a release. */
    for(i=0;i<30;i++) { poll(1,1);poll(0,1); }
    CHECK(n==0);
    poll(1,2);poll(1,5);poll(0,1);CHECK(n==0);
    poll(0,1);CHECK(n==2&&actions[0]==T4_CENTER&&values[0]==1&&values[1]==0);
    seed(0);poll(1,2);poll(1,40);CHECK(n==2&&actions[0]==T4_HOME);
    poll(1,100);poll(0,2);CHECK(n==2);
    seed(0);poll(2,2);poll(0,2);CHECK(n==2&&actions[0]==T4_BACK);
    seed(0);poll(2,42);poll(0,2);CHECK(n==2&&actions[0]==T4_MENU);
    seed(0);poll(4,2);CHECK(n==1&&actions[0]==T4_UP&&values[0]==1);
    for(i=0;i<10;i++) { poll(0,1);poll(4,1); }
    CHECK(n==1);poll(0,2);CHECK(n==2&&values[1]==0);
    seed(0);poll(8,2);poll(0,2);CHECK(n==2&&actions[0]==T4_DOWN);
    /* Suppress every key held at handoff until a debounced release. */
    seed(15);poll(15,200);poll(0,2);CHECK(n==0);
    poll(15,2);poll(0,2);CHECK(n==8);
    /* Simultaneous volume edges and 32-bit tick wrap. */
    seed(0);s.tick=0xfffffff0u;poll(1,42);poll(0,2);
    CHECK(n==2&&actions[0]==T4_HOME);
    seed(0);poll(12,2);CHECK(n==2&&actions[0]==T4_UP&&actions[1]==T4_DOWN);
    poll(0,2);CHECK(n==4&&values[2]==0&&values[3]==0);
    return 0;
}
