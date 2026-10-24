/* A complete, pinned image set through Apple's existing image-update API.
 * Bootlace reference: opibFlashManifest / opibFlashIMG3 (LLB first, then images).
 * No exploit, signature-check modification, raw NAND, partition or NVRAM code.
 * Run only after all package inputs and Apple's LLB signature were validated. */
typedef unsigned int U;typedef unsigned long S;typedef const void *CF;
extern U mach_task_self_;
extern int printf(const char *,...);extern int strcmp(const char *,const char *);
extern int sysctlbyname(const char *,void *,S *,void *,S);
extern int open(const char *,int,...);extern int read(int,void *,S);extern int close(int);
extern void *valloc(S);extern void free(void *);
extern CF IOServiceMatching(const char *);extern U IOServiceGetMatchingService(U,CF);
extern int IOServiceOpen(U,U,U,U *);extern int IOServiceClose(U);extern int IOObjectRelease(U);
extern int IOConnectCallStructMethod(U,U,const void *,S,void *,S *);
#define MAX_PACKAGE_SIZE 0x180000u
static U crc(const unsigned char *p,U n){U c=~0U;for(U i=0;i<n;i++){c^=p[i];for(int j=0;j<8;j++)c=(c>>1)^(0xedb88320U&(0U-(c&1)));}return ~c;}
static int image(const unsigned char *p,U n,U type){
 if(n<20)return 0;const U *h=(const U *)p;
 if(h[0]!=0x496d6733 || h[1]!=n || h[2]!=n-20 || h[4]!=type)return 0;
 U off=20;while(off<n){if(n-off<12)return 0;const U *t=(const U *)(p+off);if(t[1]<12 || t[1]>n-off || t[2]>t[1]-12)return 0;off+=t[1];}
 return off==n;
}
int main(int argc,char **argv){
 if(argc!=3 || strcmp(argv[1],"--apply"))return 2;
 char machine[32]={0};S ml=sizeof(machine);
 if(sysctlbyname("hw.machine",machine,&ml,0,0) || strcmp(machine,"iPod4,1"))return 3;
 int fd=open(argv[2],0);if(fd<0)return 4;
 unsigned char *b=valloc(MAX_PACKAGE_SIZE);if(!b)return 5;U done=0;
 while(done<MAX_PACKAGE_SIZE){int n=read(fd,b+done,MAX_PACKAGE_SIZE-done);if(n<0)return 6;if(!n)break;done+=n;}
 if(done<16)return 6;U package_size=done;
 unsigned char extra;if(read(fd,&extra,1)!=0)return 7;close(fd);
 if(((U *)b)[3]!=crc(b+16,package_size-16))return 8;
 U *header=(U *)b;
 if(header[0]!=0x4f423454 || header[1]!=2 || header[2]!=7)return 9;
 U kinds[7]={0x696c6c62,0x69626f74,0x64747265,0x6c6f676f,0x7265636d,0x69626f62,0x53434142};
 U offsets[7],lengths[7],off=16;
 for(U i=0;i<7;i++){
  if(off>package_size || package_size-off<16)return 10;
  U *r=(U *)(b+off);U n=r[1];off+=16;
  if(r[0]!=(i?1U:0U) || r[2]!=kinds[i] || n>package_size-off || n>0xc0000)return 11;
  if(crc(b+off,n)!=r[3] || !image(b+off,n,kinds[i]))return 12;
  offsets[i]=off;lengths[i]=n;off+=(n+3)&~3U;
 }
 if(off!=package_size)return 13;
 U service=IOServiceGetMatchingService(0,IOServiceMatching("AppleImage3NORAccess"));if(!service)return 14;
 U connection=0;int e=IOServiceOpen(service,mach_task_self_,0,&connection);
 if(e){printf("SET_OPEN_RESULT=%08x\n",e);return 15;}
 e=IOConnectCallStructMethod(connection,2,b+offsets[0],lengths[0],0,0);
 printf("SET_LLB_PREFLIGHT_RESULT=%08x\n",e);
 if(e){IOServiceClose(connection);IOObjectRelease(service);return 16;}
 for(U i=0;i<7;i++){
  printf("SET_IMAGE_%u_BEGIN type=%08x selector=%u size=%u\n",i,kinds[i],i?1:0,lengths[i]);
  e=IOConnectCallStructMethod(connection,i?1:0,b+offsets[i],lengths[i],0,0);
  printf("SET_IMAGE_%u_RESULT=%08x\n",i,e);
  if(e){printf("SET_INCOMPLETE_DO_NOT_REBOOT\n");IOServiceClose(connection);IOObjectRelease(service);return 17;}
 }
 e=IOServiceClose(connection);IOObjectRelease(service);free(b);
 printf("SET_CLOSE_RESULT=%08x\n",e);
 if(e)return 18;
 printf("COMPLETE_IMAGE_SET_API_ACCEPTED; COLD_BOOT_NOT_YET_CONFIRMED\n");return 0;
}
