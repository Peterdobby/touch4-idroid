/* Minimal RAM-only PID1. No block nodes, storage mounts, Android or ADB.
 * Read-only sysfs discovers ttyGS0's actual character-device number.
 * ACM sends status and echoes host input; all nodes live in initramfs. */
static long call(long n,long a,long b,long c,long d,long e)
{
    register long r0 __asm__("r0")=a;
    register long r1 __asm__("r1")=b;
    register long r2 __asm__("r2")=c;
    register long r3 __asm__("r3")=d;
    register long r4 __asm__("r4")=e;
    register long r7 __asm__("r7")=n;
    __asm__ volatile("svc 0" : "+r"(r0) : "r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r7) : "memory","cc");
    return r0;
}
static long open(const char *p,long flags) {return call(5,(long)p,flags,0,0,0);}
static void close(long fd) {call(6,fd,0,0,0,0);}
static void write(long fd,const char *s,long n) {if(fd>=0) call(4,fd,(long)s,n,0,0);}
static void mount(const char *what,const char *where,const char *type) {call(21,(long)what,(long)where,(long)type,0,0);}
void _start(void)
{
    long log,serial=-1,fd,n;unsigned major,minor,i;
    char buf[512];struct {long sec,nsec;} pause={1,0};unsigned tick=0;
    static const char ready[]="<5>T4_USB_ACM_01 PID1_REACHED; RAM-only; waiting for host ACM\n";
    static const char hello[]="T4_USB_ACM_01 RAM serial alive; type to test echo\r\n";
    mount("proc","/proc","proc");mount("sysfs","/sys","sysfs");
    log=open("/dev/kmsg",1);write(log,ready,sizeof(ready)-1);
    for(;;) {
        if(serial<0) {
            fd=open("/sys/class/tty/ttyGS0/dev",0);
            if(fd>=0) {
                n=call(3,fd,(long)buf,sizeof(buf),0,0);close(fd);if(n<0) n=0;major=minor=i=0;
                while(i<(unsigned)n && buf[i]>='0' && buf[i]<='9') major=major*10+buf[i++]-'0';
                if(i<(unsigned)n && buf[i++]==':') {
                    while(i<(unsigned)n && buf[i]>='0' && buf[i]<='9') minor=minor*10+buf[i++]-'0';
                    if(major>0 && major<256 && minor<256) {
                        call(14,(long)"/dev/ttyGS0",0020600,(major<<8)|minor,0,0);
                        serial=open("/dev/ttyGS0",2|04000|0400); /* nonblock, no controlling tty */
                    }
                }
            }
        }
        if(tick++==0) {
            fd=open("/sys/devices/platform/s3c-hsotg/usb_state",0);
            if(fd>=0) {
                n=call(3,fd,(long)buf,sizeof(buf),0,0);close(fd);
                if(n>0) {write(log,buf,n);write(serial,buf,n);}
            }
            write(serial,hello,sizeof(hello)-1);
        }
        if(serial>=0) {
            n=call(3,serial,(long)buf,sizeof(buf),0,0);
            if(n>0) write(serial,buf,n);
        }
        if(tick==5) tick=0;
        call(162,(long)&pause,0,0,0,0);
    }
}
