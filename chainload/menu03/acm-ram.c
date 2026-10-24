/* Existing public OpeniBoot ACM transport: RAM transfers only. No DFU,
 * firmware update, block device, environment or filesystem commands. */
#include <libusb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static libusb_device_handle *usb;
static void fail(const char *why) { fprintf(stderr,"%s\n",why); exit(2); }
static void send_bytes(const void *p,int len) {
    int n=0,e=libusb_bulk_transfer(usb,2,(unsigned char *)p,len,&n,5000);
    if(e || n!=len)fail("ACM bulk OUT incomplete");
}
static int packet(unsigned char *p,unsigned timeout) {
    int n=0,e=libusb_bulk_transfer(usb,0x81,p,512,&n,timeout);
    if(e && e!=LIBUSB_ERROR_TIMEOUT)fail(libusb_error_name(e));
    return n;
}
static int until(const char *marker,unsigned seconds) {
    char log[65536];size_t used=0;log[0]=0;
    time_t end=time(NULL)+seconds;
    while(time(NULL)<end) {
        unsigned char p[512];int n=packet(p,250);
        if(n) {
            fwrite(p,1,(size_t)n,stdout);fflush(stdout);
            if(used+(size_t)n>=sizeof(log)) {
                size_t keep=used/2;memmove(log,log+used-keep,keep);used=keep;
            }
            memcpy(log+used,p,(size_t)n);used+=(size_t)n;log[used]=0;
            if(strstr(log,marker))return 1;
        }
    }
    return 0;
}
static void command(const char *s) { send_bytes(s,(int)strlen(s)); }
static unsigned number(const char *s) {
    char *end;unsigned long x=strtoul(s,&end,0);
    if(!*s || *end || x>0xffffffffUL)fail("Invalid number");
    return (unsigned)x;
}
int main(int argc,char **argv) {
    if(argc<3)fail("read ADDRESS SIZE OUT | upload ADDRESS FILE | go ADDRESS | jump ADDRESS");
    unsigned address=number(argv[2]);
    libusb_context *ctx=NULL;if(libusb_init(&ctx))fail("libusb init failed");
    usb=libusb_open_device_with_vid_pid(ctx,0x0525,0x1280);
    if(!usb)fail("OpeniBoot USB 0525:1280 absent");
    int cfg=0;if(libusb_get_configuration(usb,&cfg))fail("configuration read failed");
    if(cfg!=1 && libusb_set_configuration(usb,1))fail("configuration failed");
    if(libusb_claim_interface(usb,0))fail("claim failed");
    if(!strcmp(argv[1],"listen")) {
        until("UNUSED_CAPTURE_END",4);
        libusb_release_interface(usb,0);libusb_close(usb);libusb_exit(ctx);return 0;
    }
    unsigned char p[512];for(int i=0;i<32 && packet(p,30);i++);
    command("version\n");
    if(!until("ACM: Done: version.",8))fail("Fresh public version round trip failed");
    char cmd[128];
    if(!strcmp(argv[1],"read")) {
        if(argc!=5)fail("read ADDRESS SIZE OUT");
        unsigned size=number(argv[3]);
        if(address<0x40000000 || !size || size>0x400000 ||
           address>0x50000000-size)fail("Read outside bounded A4 RAM");
        FILE *f=fopen(argv[4],"wbx");if(!f)fail("Output exists or cannot be created");
        snprintf(cmd,sizeof(cmd),"recvfile 0x%x %u\n",address,size);command(cmd);
        int n=packet(p,5000);unsigned got_addr=0,got_size=0;
        if(n<=0 || n>=512)fail("Missing file header");
        p[n]=0;
        if(sscanf((char *)p,"ACM: Starting File: %u %u",&got_addr,&got_size)!=2 ||
           got_addr!=address || got_size!=size || p[n-1]!='\n')fail("Unexpected file header");
        unsigned received=0;
        while(received<size) {
            n=packet(p,5000);
            if(n<=0 || (unsigned)n>size-received)fail("Incomplete RAM read");
            if(fwrite(p,1,(size_t)n,f)!=(size_t)n)fail("Host file write failed");
            received+=(unsigned)n;
        }
        if(fclose(f))fail("Host file close failed");
        printf("RAM_READ_COMPLETE address=%08x bytes=%u file=%s\n",address,size,argv[4]);
    } else if(!strcmp(argv[1],"upload")) {
        if(argc!=4)fail("upload ADDRESS FILE");
        FILE *f=fopen(argv[3],"rb");if(!f)fail("Cannot read input");
        fseek(f,0,SEEK_END);long size=ftell(f);rewind(f);
        int normal=address>=0x41000000 && address<0x48000000 && size>0 &&
                   size<=0x4000000 && address<=0x48000000-(unsigned)size;
        int dt_slot=address==0x4e000000 && size==62824;
        if(!normal && !dt_slot)fail("Upload outside experiment RAM");
        snprintf(cmd,sizeof(cmd),"sendfile 0x%x %ld\n",address,size);command(cmd);
        long sent=0;
        while(sent<size) {
            int want=size-sent>512 ? 512:(int)(size-sent);
            if(fread(p,1,(size_t)want,f)!=(size_t)want)fail("Input read failed");
            send_bytes(p,want);sent+=want;
        }
        fclose(f);command("version\n");
        if(!until("ACM: Done: version.",10))fail("RAM upload completion unconfirmed");
        command("jump 0x684\n");
        if(!until("ACM: Done: jump 0x684.",8))fail("RAM instruction cache synchronization unconfirmed");
        printf("RAM_UPLOAD_COMPLETE address=%08x bytes=%ld\n",address,size);
    } else if(!strcmp(argv[1],"go") || !strcmp(argv[1],"jump")) {
        int normal=address>=0x41000000 && address<0x48000000;
        int menu=!strcmp(argv[1],"jump") && address>=0x44000 && address<0x100000;
        if(argc!=3 || (!normal && !menu))fail("Execution outside experiment RAM");
        snprintf(cmd,sizeof(cmd),"%s 0x%x\n",argv[1],address);command(cmd);
        /* Transport disconnect is not proof of success. Keep this result explicit. */
        puts("RAM_EXEC_REQUEST_SENT; verify the next boot stage independently");
    } else fail("Unsupported operation");
    libusb_release_interface(usb,0);libusb_close(usb);libusb_exit(ctx);return 0;
}
