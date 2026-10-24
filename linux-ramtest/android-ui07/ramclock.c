/* Set only Linux's volatile wall clock. No RTC/alarm ioctl, device or file open. */
static long call(long n,long a,long b,long c) {
    register long r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c,r7 __asm__("r7")=n;
    __asm__ volatile("svc 0":"+r"(r0):"r"(r1),"r"(r2),"r"(r7):"memory","cc");return r0;
}
void clock_main(unsigned long *stack) __attribute__((used,noreturn));
void clock_main(unsigned long *stack) {
    const char *p;unsigned long epoch=0;long rc;struct {long sec,usec;} tv;
    if(stack[0]!=2)goto bad;
    p=(const char *)stack[2];if(!*p)goto bad;
    while(*p) {if(*p<'0'||*p>'9'||epoch>214748364ul)goto bad;epoch=epoch*10+(*p++-'0');}
    if(epoch<1262304000ul||epoch>2147483647ul)goto bad;
    tv.sec=(long)epoch;tv.usec=0;rc=call(79,(long)&tv,0,0);
    if(rc<0)goto bad;
    {static const char msg[]="<5>T4_RAM_CLOCK_READY: Linux time only; RTC untouched\n";call(4,1,(long)msg,sizeof(msg)-1);}
    call(1,0,0,0);for(;;){}
bad:call(1,1,0,0);for(;;){}
}
void _start(void) __attribute__((naked,noreturn));
void _start(void) {__asm__ volatile("mov r0,sp\nb clock_main");}
