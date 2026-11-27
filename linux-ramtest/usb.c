/* Fixed RAM staging / Linux handoff sequence on the existing public ACM.
 * No interactive command shell and no filesystem/storage commands.
 */
#include <libusb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#ifndef T4_TEST_NAME
#define T4_TEST_NAME "T4_LINUX_RAM_02"
#endif

static libusb_device_handle *h;
static int version_seen,received,refused,cmdline_seen;
static unsigned framebuffer_seen;
static int send_failed;
static void send_bytes(const unsigned char *p,int size)
{
    int n=0,e=libusb_bulk_transfer(h,2,(unsigned char *)p,size,&n,5000);
    if(e || n!=size) {fprintf(stderr,"ACM OUT failed: %s (%d/%d)\n",libusb_error_name(e),n,size);send_failed=1;}
}
static void command(const char *s) {send_bytes((const unsigned char *)s,(int)strlen(s));}
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
            if(strstr(text,"ACM: Received file"))received=1;
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
        if(e && e!=LIBUSB_ERROR_TIMEOUT)return 0;
    }
    return 0;
}
/* The public ACM stalls on long single transfers, so send 1 MiB pieces, each
 * confirmed by the device, and pause briefly every 16 KiB. */
/* A USB reset re-arms the stalled ACM receive without rebooting the device. */
static libusb_context *usb_ctx;
static int recover(void)
{
    fputs("[HOST] Transfer stalled; resetting the USB connection.\n",stderr);
    libusb_reset_device(h);libusb_close(h);h=NULL;
    sleep(3); /* the device re-enumerates about a second later */
    for(int i=0;i<20 && !h;i++) {sleep(1);h=libusb_open_device_with_vid_pid(usb_ctx,0x0525,0x1280);}
    if(!h) return 0;
    libusb_set_auto_detach_kernel_driver(h,1);
    if(libusb_claim_interface(h,0)) return 0;
    send_failed=0;command("version\n");
    return !send_failed && receive_until("ACM: Done: version.",10);
}
static int upload(const char *path,unsigned address,long limit)
{
    FILE *f=fopen(path,"rb");if(!f)return 0;
    if(fseek(f,0,SEEK_END)) {fclose(f);return 0;}
    long size=ftell(f);rewind(f);
    if(size<=0 || size>limit) {fclose(f);return 0;}
    int tries=0;
    for(long done=0;done<size;) {
        if(fseek(f,done,SEEK_SET)) {fclose(f);return 0;}
        send_failed=0;
        long piece=size-done>(1L<<20) ? (1L<<20) : size-done;
        char line[128];received=0;
        snprintf(line,sizeof(line),"sendfile 0x%lx %ld\n",address+done,piece);command(line);
        for(long pos=0;pos<piece && !send_failed;) {
            unsigned char b[512];int count=piece-pos>512 ? 512 : (int)(piece-pos);
            if(fread(b,1,(size_t)count,f)!=(size_t)count) {fclose(f);return 0;}
            send_bytes(b,count);pos+=count;
            if(!(pos&0x3fff))usleep(1000);
        }
        /* Existing ACM queues progress until a following command kicks IN. */
        command("version\n");
        if(send_failed || !receive_until("ACM: Done: version.",10) || !received) {
            if(++tries>3 || !recover()) {fclose(f);return 0;}
            continue; /* resend the same piece */
        }
        done+=piece;tries=0;
    }
    fclose(f);
    return 1;
}
int main(int argc,char **argv)
{
    if(argc!=7 || (strcmp(argv[1],"--stage") && strcmp(argv[1],"--boot")))return 1;
    char *end;unsigned long stage=strtoul(argv[5],&end,0);
    if(*end || !(stage&1) || stage<0x44000000 || stage>=0x44010000)return 1;
    unsigned long boot=strtoul(argv[6],&end,0);
    if(*end || !(boot&1) || boot<0x44000000 || boot>=0x44010000)return 1;
    libusb_context *ctx=NULL;if(libusb_init(&ctx))return 2;
    usb_ctx=ctx;
    h=libusb_open_device_with_vid_pid(ctx,0x0525,0x1280);
    if(!h) {fputs("Start the proven published OpeniBoot RAM baseline first.\n",stderr);return 2;}
    libusb_set_auto_detach_kernel_driver(h,1); /* Linux may bind cdc_acm */
    if(libusb_claim_interface(h,0)) {fputs("Cannot claim OpeniBoot USB interface.\n",stderr);return 2;}
    puts("OpeniBoot USB 0525:1280 opened.");
    command("version\n");
    if(!receive_until("ACM: Done: version.",5) || !version_seen)return 3;
    if(!upload(argv[2],0x42000000,12*1024*1024) ||
       !upload(argv[3],0x43000000,12*1024*1024) ||
       !upload(argv[4],0x44000000,65536))return 3;
    command("jump 0x684\n");
    if(!receive_until("ACM: Done: jump 0x684.",5))return 3;
    char line[128];snprintf(line,sizeof(line),"jump 0x%lx\n",stage);command(line);
    if(!receive_until("T4_LINUX_STAGED_NOT_EXECUTED",120) || !cmdline_seen) {
        fputs("[HOST] Stage/command-line validation failed; Linux handoff stopped.\n",stderr);
        return 4;
    }
    /* The following version round trip confirms stage returned to console;
     * its preceding Done: jump may share the already consumed marker packet. */
    command("version\n");
    if(!receive_until("ACM: Done: version.",5))return 4;
    puts("[HOST] RAM payload CRCs checked; stage returned; Linux has NOT executed.");fflush(stdout);
    if(!strcmp(argv[1],"--boot")) {
        puts("[HOST] Requesting native Linux handoff. Photograph/read the screen.");
        puts("[HOST] USB disconnect or this host message is NOT kernel boot evidence.");fflush(stdout);
        snprintf(line,sizeof(line),"jump 0x%lx\n",boot);command(line);
        if(receive_until("native boot_linux returned unexpectedly",60) || refused) {
            fputs("[HOST] Linux handoff refused or returned; boot failed.\n",stderr);
            return 4;
        }
        puts("[HOST] Handoff request sent. Result pending screen/serial Linux logs.");
    }
    libusb_release_interface(h,0);libusb_close(h);libusb_exit(ctx);
    return 0; /* command delivery/staging only, never Linux success */
}
