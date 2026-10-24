/* PID 1 for RAM-only validation. Opens only the in-memory /dev/kmsg node. */
static long call3(long n,long a,long b,long c)
{
    register long r0 __asm__("r0")=a;
    register long r1 __asm__("r1")=b;
    register long r2 __asm__("r2")=c;
    register long r7 __asm__("r7")=n;
    __asm__ volatile("svc 0" : "+r"(r0) : "r"(r1),"r"(r2),"r"(r7) : "memory","cc");
    return r0;
}
void _start(void)
{
    static const char marker[]="<5>T4_LINUX_RAM_01: PID1_REACHED; no block device opened; no storage mounted\n";
    struct { long sec,nsec; } delay={5,0};
    long fd=call3(5,(long)"/dev/kmsg",1,0);
    for(;;) {
        if(fd>=0) call3(4,fd,(long)marker,sizeof(marker)-1);
        call3(162,(long)&delay,0,0);
    }
}
