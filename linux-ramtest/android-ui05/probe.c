/* Freestanding RAM-only bootstrap/probe. No block device or storage access. */
static long sys3(long n,long a,long b,long c)
{
    register long r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
    register long r7 __asm__("r7")=n;
    __asm__ volatile("svc 0":"+r"(r0):"r"(r1),"r"(r2),"r"(r7):"memory","cc");
    return r0;
}
static void say(long fd,const char *s)
{
    long n=0;while(s[n])n++;if(fd>=0)sys3(4,fd,(long)s,n);
}
static void number(long fd,const char *label,long n)
{
    char b[96];int i=0,shift;
    static const char hex[]="0123456789abcdef";
    while(*label && i<80)b[i++]=*label++;
    b[i++]='0';b[i++]='x';
    for(shift=28;shift>=0;shift-=4)b[i++]=hex[((unsigned)n>>shift)&15];
    b[i++]='\n';b[i]=0;say(fd,b);
}
void _start(void)
{
#ifndef ANDROID_BOOTSTRAP
    /* Native node in /dev tmpfs only. Handles a delayed device event safely. */
    sys3(14,(long)"/dev/kmsg",0020600,(1<<8)|11);
#endif
    long fd=sys3(5,(long)"/dev/kmsg",1,0);
    struct {long sec,nsec;} delay={5,0};
#ifdef ANDROID_BOOTSTRAP
    char *argv[]={"/init",0};
    char *env[]={"PATH=/sbin","ANDROID_ROOT=/system","ANDROID_DATA=/data",0};
    long error;
    say(fd,"<5>T4_ANDROID_BOOTSTRAP_EXEC: androidi4 original init next; not yet Android success\n");
    /* Preserve PID 1, replace bootstrap with the exact original Android ELF. */
    error=sys3(11,(long)"/android-init",(long)argv,(long)env);
    say(fd,"<0>T4_ANDROID_EXEC_FAILED\n");number(fd,"<0>execve return=",error);
#else
    long parent=sys3(64,0,0,0);
    number(fd,"<5>T4_ANDROID_SERVICE_PARENT=",parent);
    number(fd,"<5>T4_ANDROID_SERVICE_PID=",sys3(20,0,0,0));
    long coldboot=sys3(33,(long)"/dev/.coldboot_done",0,0);
    long property=sys3(33,(long)"/data/property",0,0);
    static const struct {unsigned short family;char path[108];} addr={1,"/dev/socket/property_service"};
    long socket=sys3(281,1,1,0);
    long connected=socket<0 ? socket : sys3(283,socket,(long)&addr,31);
    if(socket>=0)sys3(6,socket,0,0);
    number(fd,"<5>T4_ENV coldboot_access=",coldboot);
    number(fd,"<5>T4_ENV property_dir_access=",property);
    number(fd,"<5>T4_ENV property_socket_connect=",connected);
    if(parent==1 && coldboot==0 && property==0 && connected==0)
        say(fd,"<5>ANDROID_INIT_ENVIRONMENT_CONFIRMED: coldboot, RAM property directory, live Unix property socket\n");
    else say(fd,"<0>T4_ANDROID_ENVIRONMENT_CHECK_FAILED\n");
    if(parent!=1)say(fd,"<0>T4_ANDROID_SERVICE_UNEXPECTED_PARENT\n");
#endif
    for(;;) {
#ifndef ANDROID_BOOTSTRAP
        if(parent==1)say(fd,"<5>ANDROID_INIT_SERVICE_REACHED; RAM-only; no block device opened\n");
#endif
        sys3(162,(long)&delay,0,0);
    }
}
