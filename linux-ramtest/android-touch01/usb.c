/* Fixed RAM staging / Linux handoff sequence on the existing public ACM.
 * No interactive command shell and no filesystem/storage commands.
 */
#include <libusb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <errno.h>
#include <unistd.h>
#ifndef T4_TEST_NAME
#define T4_TEST_NAME "T4_LINUX_RAM_02"
#endif

static libusb_device_handle *h;
static libusb_context *ctx;
static unsigned recovery_left=2;
static int version_seen,received,refused,cmdline_seen;
static unsigned framebuffer_seen;
static char expected_received[96];
#define RAM_UPLOAD_CHUNK (1L*1024*1024)
static int send_bytes(const unsigned char *p,int size)
{
    int n=0,e=libusb_bulk_transfer(h,2,(unsigned char *)p,size,&n,5000);
    if(e || n!=size) {fprintf(stderr,"ACM OUT failed: %s (%d/%d)\n",libusb_error_name(e),n,size);return 0;}
    return 1;
}
static int command(const char *s) {return send_bytes((const unsigned char *)s,(int)strlen(s));}
static int receive_until(const char *marker,unsigned seconds)
{
    char text[65536];size_t used=0;time_t end=time(NULL)+seconds;text[0]=0;
    while(time(NULL)<end) {
        unsigned char b[512];int n=0,e=libusb_bulk_transfer(h,0x81,b,sizeof(b),&n,500);
        if(n>0) {
            fwrite(b,1,(size_t)n,stdout);fflush(stdout);
            if(used+(size_t)n>=sizeof(text)) {size_t drop=used/2;memmove(text,text+drop,used-drop);used-=drop;}
            memcpy(text+used,b,(size_t)n);used+=(size_t)n;text[used]=0;
            if(strstr(text,"openiboot 0.3 commit c5cee8c for iPod Touch 4G"))version_seen=1;
            if(expected_received[0] && strstr(text,expected_received))received=1;
            char *fb=strstr(text,"inherited framebuffer=");
            if(fb) (void)sscanf(fb,"inherited framebuffer=%x",&framebuffer_seen);
            if(framebuffer_seen>=0x48000000 && framebuffer_seen<0x50000000) {
                char expected[64];
                snprintf(expected,sizeof(expected)," t4fb=0x%08x ",framebuffer_seen-0x40000000);
                if(strstr(text,"prepared cmdline: console=t4fb0 loglevel=8 ") &&
                   strstr(text,expected) && strstr(text," t4_test=" T4_TEST_NAME))
                    cmdline_seen=1;
            }
            if(strstr(text,"[T4_LINUX] REFUSED")) {refused=1;return 0;}
            if(marker && strstr(text,marker))return 1;
        }
        if(e && e!=LIBUSB_ERROR_TIMEOUT) {
            if(e==LIBUSB_ERROR_NO_DEVICE && marker &&
               !strcmp(marker,"native boot_linux returned unexpectedly"))return 0;
            fprintf(stderr,"[HOST] ACM IN failed while waiting for '%s': %s\n",
                    marker ? marker : "handoff/disconnect",libusb_error_name(e));
            return 0;
        }
    }
    if(marker) fprintf(stderr,"[HOST] Timed out after %u seconds waiting for '%s'.\n",seconds,marker);
    return 0;
}
static int recover_session(void)
{
    if(!recovery_left)return 0;
    recovery_left--;
    fprintf(stderr,"[HOST] Recovering USB session only; %u recovery attempt(s) left.\n",recovery_left);
    /* c5cee8c usbIRQHandler(RESET) -> resetUSB clears endpoint queues;
     * enumeration -> acm_started clears recv_left and re-arms OUT. A USB
     * port reset does not reboot the CPU or run any storage command.
     * Never resend bytes into an unconfirmed, possibly still active file
     * receiver: require reset + fresh pinned version before retrying. */
    int e=libusb_reset_device(h);
    (void)libusb_release_interface(h,0);libusb_close(h);h=NULL;
    if(e) {fprintf(stderr,"[HOST] USB reset failed: %s; stopped.\n",libusb_error_name(e));return 0;}
    for(unsigned n=0;n<30 && !h;n++) {
        usleep(100000);
        h=libusb_open_device_with_vid_pid(ctx,0x0525,0x1280);
    }
    if(!h) {fputs("[HOST] OpeniBoot did not re-enumerate after USB reset.\n",stderr);return 0;}
    e=libusb_claim_interface(h,0);
    if(e) {fprintf(stderr,"[HOST] Reclaim after USB reset failed: %s.\n",libusb_error_name(e));return 0;}
    version_seen=received=0;expected_received[0]=0;
    if(!command("version\n") || !receive_until("ACM: Done: version.",8) || !version_seen) {
        fputs("[HOST] Fresh OpeniBoot version NOT confirmed; no payload retry.\n",stderr);return 0;
    }
    puts("[HOST] USB session restored; retrying only the unconfirmed RAM range.");fflush(stdout);
    return 1;
}
static int upload(const char *path,unsigned address,long limit)
{
    FILE *f=fopen(path,"rb");
    if(!f) {fprintf(stderr,"[HOST] Cannot open %s: %s\n",path,strerror(errno));return 0;}
    if(fseek(f,0,SEEK_END)) {fprintf(stderr,"[HOST] Cannot seek %s.\n",path);fclose(f);return 0;}
    long size=ftell(f);rewind(f);
    if(size<=0 || size>limit) {fprintf(stderr,"[HOST] Invalid RAM payload size: %ld (limit %ld).\n",size,limit);fclose(f);return 0;}
    printf("[HOST] RAM upload %s: %ld bytes to %08x\n",path,size,address);fflush(stdout);
    /* c5cee8c acm_received() copies min(packet length, recv_left), then
     * rearms its 512-byte OUT buffer. Send full packets, padding only on the
     * wire: sendfile still declares the EXACT payload length, so no padding
     * reaches RAM. Keep large uploads bounded by a version/receive ACK at
     * each 1 MiB boundary. No command is sent inside a file's data stream.
     * Give the legacy receive/parse task time to finish at command boundaries
     * and yield 1ms per 16KiB during data. This is a transport experiment,
     * not a claim that the hardware stall's root cause has been established. */
    for(long offset=0;offset<size;) {
        long chunk=size-offset>RAM_UPLOAD_CHUNK ? RAM_UPLOAD_CHUNK : size-offset;
        unsigned start=address+(unsigned)offset,end=start+(unsigned)chunk;
        char line[128];received=0;
        if(fseek(f,offset,SEEK_SET)) {fclose(f);return 0;}
        snprintf(expected_received,sizeof(expected_received),
                 "ACM: Received file (finished at 0x%08x)!",end);
        snprintf(line,sizeof(line),"sendfile 0x%x %ld\n",start,chunk);
        int sent=command(line);usleep(2000);
        for(long pos=0;sent && pos<chunk;) {
            unsigned char b[512]={0};int count=chunk-pos>512 ? 512 : (int)(chunk-pos);
            if(fread(b,1,(size_t)count,f)!=(size_t)count) {
                fprintf(stderr,"[HOST] File read failed at %ld/%ld bytes: %s.\n",offset+pos,size,path);
                fclose(f);return 0;
            }
            sent=send_bytes(b,sizeof(b));pos+=count;
            if(!(pos%16384))usleep(1000);
        }
        if(sent)printf("[HOST] Sent %ld/%ld payload bytes; waiting for RAM ACK at %08x.\n",
                       offset+chunk,size,end);
        else printf("[HOST] OUT incomplete for range %08x..%08x; range remains unconfirmed.\n",start,end);
        fflush(stdout);
        /* ACM queues file output until the following command kicks IN. */
        usleep(2000);
        if(!sent || !command("version\n") || !receive_until("ACM: Done: version.",10) || !received) {
            fprintf(stderr,"[HOST] RAM upload NOT confirmed: %s; range %08x..%08x.\n"
                    "[HOST] No Linux stage/boot has been requested.\n",
                    path,start,end);
            if(recover_session())continue;
            fputs("[HOST] STOP: recovery unavailable/failed. Re-enter DFU and restart the published RAM baseline.\n",stderr);
            fclose(f);return 0;
        }
        offset+=chunk;
        printf("[HOST] RAM upload confirmed: %ld/%ld bytes.\n",offset,size);fflush(stdout);
        usleep(2000);
    }
    fclose(f);
    expected_received[0]=0;
    return 1;
}
int main(int argc,char **argv)
{
    if(argc!=7 || (strcmp(argv[1],"--stage") && strcmp(argv[1],"--boot")))return 1;
    char *end;unsigned long stage=strtoul(argv[5],&end,0);
    if(*end || !(stage&1) || stage<0x44000000 || stage>=0x44010000)return 1;
    unsigned long boot=strtoul(argv[6],&end,0);
    if(*end || !(boot&1) || boot<0x44000000 || boot>=0x44010000)return 1;
    if(libusb_init(&ctx))return 2;
    h=libusb_open_device_with_vid_pid(ctx,0x0525,0x1280);
    if(!h) {fputs("Start the proven published OpeniBoot RAM baseline first.\n",stderr);return 2;}
    if(libusb_claim_interface(h,0))return 2;
    puts("OpeniBoot USB 0525:1280 opened.");
    puts("[HOST] Upload protocol v2: 1MiB ACKs, paced OUT, at most 2 USB-only resets.");
    if(!command("version\n") || !receive_until("ACM: Done: version.",5) || !version_seen)return 3;
    if(!upload(argv[2],0x42000000,8*1024*1024) ||
       !upload(argv[3],0x44800000,56*1024*1024) ||
       !upload(argv[4],0x44000000,65536))return 3;
    if(!command("jump 0x684\n") || !receive_until("ACM: Done: jump 0x684.",5))return 3;
    char line[128];snprintf(line,sizeof(line),"jump 0x%lx\n",stage);
    if(!command(line))return 4;
    if(!receive_until("T4_LINUX_STAGED_NOT_EXECUTED",120) || !cmdline_seen) {
        fputs("[HOST] Stage/command-line validation failed; Linux handoff stopped.\n",stderr);
        return 4;
    }
    /* The following version round trip confirms stage returned to console;
     * its preceding Done: jump may share the already consumed marker packet. */
    if(!command("version\n") || !receive_until("ACM: Done: version.",5))return 4;
    puts("[HOST] RAM payload CRCs checked; stage returned; Linux has NOT executed.");fflush(stdout);
    if(!strcmp(argv[1],"--boot")) {
        puts("[HOST] Requesting native Linux handoff. Photograph/read the screen.");
        puts("[HOST] USB disconnect or this host message is NOT kernel boot evidence.");fflush(stdout);
        snprintf(line,sizeof(line),"jump 0x%lx\n",boot);
        if(!command(line))return 4;
        if(receive_until("native boot_linux returned unexpectedly",15) || refused) {
            fputs("[HOST] Linux handoff refused or returned; boot failed.\n",stderr);
            return 4;
        }
        puts("[HOST] Handoff request sent. Result pending screen/serial Linux logs.");
    }
    libusb_release_interface(h,0);libusb_close(h);libusb_exit(ctx);
    return 0; /* command delivery/staging only, never Linux success */
}
