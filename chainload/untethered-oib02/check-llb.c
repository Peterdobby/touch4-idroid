/* AppleImage3NORAccess selector 2 preflight only.
 * Audited stock 10B500 code: externalMethod 80c01098 -> 80c01620.
 * That path validates the signed LLB and does not call 80c0178c (begin update).
 * No write selectors 0/1/3, raw storage, NVRAM or kernel patches. */
typedef unsigned int U;typedef unsigned long S;typedef const void *CF;
extern U mach_task_self_;
extern int printf(const char *,...);extern int open(const char *,int,...);
extern int read(int,void *,S);extern int close(int);extern void *valloc(S);extern void free(void *);
extern CF IOServiceMatching(const char *);extern U IOServiceGetMatchingService(U,CF);
extern int IOServiceOpen(U,U,U,U *);extern int IOServiceClose(U);extern int IOObjectRelease(U);
extern int IOConnectCallStructMethod(U,U,const void *,S,void *,S *);
int main(int argc,char **argv){
 if(argc!=2)return 2;
 int fd=open(argv[1],0);if(fd<0)return 3;
 unsigned char *b=valloc(262144);if(!b)return 4;U n=0;
 for(;;){int count=read(fd,b+n,262144-n);if(count<0)return 5;if(!count)break;n+=count;if(n==262144)return 6;}
 close(fd);if(n<20 || ((U *)b)[0]!=0x496d6733 || ((U *)b)[4]!=0x696c6c62 || ((U *)b)[1]!=n)return 7;
 U service=IOServiceGetMatchingService(0,IOServiceMatching("AppleImage3NORAccess"));if(!service)return 8;
 U conn=0;int e=IOServiceOpen(service,mach_task_self_,0,&conn);if(e){printf("OPEN=%08x\n",e);return 9;}
 e=IOConnectCallStructMethod(conn,2,b,n,0,0);
 printf("SIGNED_LLB_PREFLIGHT selector=2 bytes=%u result=%08x\n",n,e);
 int closed=IOServiceClose(conn);printf("CLOSE=%08x NO_WRITE_SELECTORS_CALLED\n",closed);
 IOObjectRelease(service);free(b);return e?10:closed?11:0;
}
