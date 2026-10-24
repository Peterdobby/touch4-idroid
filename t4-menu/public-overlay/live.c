/* Fixed RAM-only uploader for the already running, proven public baseline.
 * No interactive command shell and no persistent-storage commands. */
#include <libusb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static libusb_device_handle *h;
static int version_seen;
static int file_seen;
static int ios_request_seen;
static void send(unsigned char *p,int len) {
    int n=0,e=libusb_bulk_transfer(h,2,p,len,&n,3000);
    if(e || n!=len) { fprintf(stderr,"bulk send failed: %d/%d (%s)\n",n,len,libusb_error_name(e));exit(2); }
}
static int receive_until(const char *marker,unsigned seconds) {
    char text[65536];size_t used=0;
    text[0]=0;
    time_t end=time(NULL)+seconds;
    while(time(NULL)<end) {
        unsigned char b[512];int n=0;
        int e=libusb_bulk_transfer(h,0x81,b,sizeof(b),&n,500);
        if(n>0) {
            fwrite(b,1,(size_t)n,stdout);fflush(stdout);
            if(used+(size_t)n>=sizeof(text)) {memmove(text,text+used/2,used-used/2);used-=used/2;}
            memcpy(text+used,b,(size_t)n);used+=(size_t)n;text[used]=0;
            if(strstr(text,"openiboot 0.3 commit c5cee8c for iPod Touch 4G"))version_seen=1;
            if(strstr(text,"ACM: Received file"))file_seen=1;
            if(strstr(text,"[PUBLIC_MENU_01] IOS_BOOT_REQUEST"))ios_request_seen=1;
            if(marker && strstr(text,marker)) return 1;
        }
        if(e && e!=LIBUSB_ERROR_TIMEOUT) return 0;
    }
    return marker==NULL;
}
/*
 * First iOS-return test is deliberately host-assisted:
 * the menu emits IOS_BOOT_REQUEST on Home; this still-connected host sends
 * the published OpeniBoot console's native "reboot" command. No new loader,
 * storage writer, or guessed firmware function address is introduced.
 */
static int monitor_menu_and_reboot(unsigned seconds) {
    char text[65536];
    size_t used=0;
    text[0]=0;
    int attempted=0;
    time_t end=time(NULL)+seconds;
    puts("[HOST] Menu ready. Select iOS and press Home within the next 120 seconds.");
    fflush(stdout);

    while(time(NULL)<end) {
        if(!attempted && ios_request_seen) {
            static unsigned char command[]="reboot\n";
            int written=0;
            int send_error=libusb_bulk_transfer(h,0x02,command,
                sizeof(command)-1,&written,3000);
            attempted=1;
            end=time(NULL)+20;
            if(send_error || written!=(int)sizeof(command)-1) {
                fprintf(stderr,
                    "\n[HOST] reboot command transfer incomplete (%d/%lu, %s); result is uncertain.\n",
                    written,(unsigned long)(sizeof(command)-1),
                    libusb_error_name(send_error));
            } else {
                puts("\n[HOST] Sent native OpeniBoot command: reboot");
                puts("[HOST] Waiting for reset/boot handoff; USB disconnect alone does not prove iOS reached the home screen.");
                fflush(stdout);
            }
        }
        unsigned char b[512];
        int n=0;
        int e=libusb_bulk_transfer(h,0x81,b,sizeof(b),&n,500);
        if(n>0) {
            fwrite(b,1,(size_t)n,stdout);
            fflush(stdout);
            if(used+(size_t)n>=sizeof(text)) {
                size_t drop=used/2;
                memmove(text,text+drop,used-drop);
                used-=drop;
            }
            memcpy(text+used,b,(size_t)n);
            used+=(size_t)n;
            text[used]=0;
            if(strstr(text,"[PUBLIC_MENU_01] IOS_BOOT_REQUEST"))
                ios_request_seen=1;
            if(attempted && strstr(text,"ACM: Done: reboot.")) {
                puts("\n[HOST] OpeniBoot returned from 'reboot'; reset was not confirmed.");
                puts("[HOST] Save this log and report whether the device stayed in OpeniBoot, entered recovery, or booted iOS.");
                return 2;
            }
        }
        if(e && e!=LIBUSB_ERROR_TIMEOUT) {
            if(attempted) {
                fprintf(stderr,
                    "\n[HOST] USB transport ended after the reboot request (%s). This is consistent with a reset handoff, but verify the Apple logo/iOS screen independently.\n",
                    libusb_error_name(e));
                return 0;
            }
            fprintf(stderr,"\nUSB monitor failed before an iOS request: %s\n",
                    libusb_error_name(e));
            return 3;
        }
    }
    if(!attempted) {
        puts("[HOST] Timed out without an iOS Home request; the RAM menu remains active.");
        return 1;
    }
    puts("[HOST] Reboot command was sent, but no USB handoff or command completion was observed; reboot remains unconfirmed.");
    return 2;
}

int main(int argc,char **argv) {
    if(argc!=3)return 1;
    char *end;unsigned long entry=strtoul(argv[2],&end,0);
    if(*end || !(entry&1) || entry<0x45000000 || entry>0x45010000)return 1;
    FILE *f=fopen(argv[1],"rb");if(!f)return 1;
    fseek(f,0,SEEK_END);long size=ftell(f);rewind(f);
    if(size<=0 || size>65536)return 1;
    unsigned char *data=malloc((size_t)size);if(!data || fread(data,1,(size_t)size,f)!=(size_t)size)return 1;fclose(f);
    libusb_context *ctx=NULL;if(libusb_init(&ctx))return 1;
    h=libusb_open_device_with_vid_pid(ctx,0x525,0x1280);if(!h)return 2;
    if(libusb_claim_interface(h,0))return 2;
    /* Check the currently running version before uploading RAM bytes. */
    char cmd[128];
    unsigned char version[]="version\n";send(version,sizeof(version)-1);
    if(!receive_until("ACM: Done: version.",5) || !version_seen)return 3;
    snprintf(cmd,sizeof(cmd),"sendfile 0x45000000 %ld\n",size);
    send((unsigned char *)cmd,(int)strlen(cmd));
    /* acm_send intentionally defers console output while receiving a file.
     * Bulk OUT waits for the parser to arm its next receive; do not wait for
     * the queued 'Started receiving' message before sending the bytes. */
    for(long pos=0;pos<size;) {int n=(size-pos)>512 ? 512 : (int)(size-pos);send(data+pos,n);pos+=n;}
    free(data);
    /* This ACM implementation queues its completion text while busy and
     * doesn't kick bulk IN after clearing busy. A read-only version request
     * starts output again once the file receiver has armed command input. */
    unsigned char after[]="version\n";send(after,sizeof(after)-1);
    if(!receive_until("ACM: Done: version.",5) || !file_seen)return 3;
    /* Original ClearCPUCaches at 0x684 cleans D-cache and invalidates I-cache,
     * then returns. No MMU, peripheral or storage reinitialisation. */
    unsigned char clean[]="jump 0x684\n";send(clean,sizeof(clean)-1);
    if(!receive_until("ACM: Done: jump 0x684.",5))return 3;
    snprintf(cmd,sizeof(cmd),"jump 0x%lx\n",entry);send((unsigned char *)cmd,(int)strlen(cmd));
    if(!receive_until("[PUBLIC_MENU_01] draw returned; entries=3",10))return 4;
    puts("\nPUBLIC_MENU_DRAW_CONFIRMED");fflush(stdout);
    int boot_result=monitor_menu_and_reboot(120);
    libusb_release_interface(h,0);libusb_close(h);libusb_exit(ctx);
    return boot_result;
}
