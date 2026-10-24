/* Bounded read-only ACM logger. Does not upload files or expose a command shell. */
#include <libusb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    unsigned watch=0;
    if(argc==3 && !strcmp(argv[1],"--watch")) {
        char *end;
        unsigned long n=strtoul(argv[2],&end,10);
        if(*end || n<1 || n>300) return 1;
        watch=(unsigned)n;
    } else if(argc!=1) { fputs("Usage: console [--watch 1..300]\n",stderr); return 1; }
    libusb_context *ctx=NULL;
    if(libusb_init(&ctx)) return 1;
    libusb_device_handle *h=NULL;
    time_t end=time(NULL)+20;
    while(time(NULL)<end && !h) {
        h=libusb_open_device_with_vid_pid(ctx,0x0525,0x1280);
        if(!h) usleep(250000);
    }
    if(!h) { fputs("No ACM device; no UI result available.\n",stderr);libusb_exit(ctx);return 2; }
    puts("OpeniBoot USB ACM logger connected.");fflush(stdout);
    int e,n,config=0,claimed=0,result=3,confirmed=0;
    char data[65536];size_t used=0;
    e=libusb_get_configuration(h,&config);
    if(e) goto done;
    if(config!=1 && libusb_set_configuration(h,1)) goto done;
    e=libusb_claim_interface(h,0); if(e) goto done;claimed=1;
    unsigned char command[]="t4_diag\n";
    e=libusb_bulk_transfer(h,0x02,command,sizeof(command)-1,&n,2000);
    if(e || n!=(int)sizeof(command)-1) goto done;
    end=time(NULL)+(watch ? watch : 12);
    while(time(NULL)<end) {
        unsigned char packet[512];n=0;
        e=libusb_bulk_transfer(h,0x81,packet,sizeof(packet),&n,500);
        if(n>0) {
            fwrite(packet,1,(size_t)n,stdout);fflush(stdout);
            if(used+(size_t)n>=sizeof(data)) { memmove(data,data+used/2,used-used/2);used-=used/2; }
            memcpy(data+used,packet,(size_t)n);used+=(size_t)n;data[used]=0;
            if(strstr(data,"ACM: Done: t4_diag.")) confirmed=1;
        }
        if(confirmed && !watch) break;
        if(e && e!=LIBUSB_ERROR_TIMEOUT) { fprintf(stderr,"ACM read: %s\n",libusb_error_name(e));break; }
    }
    if(confirmed) { puts("\nT4_DIAGNOSTIC_LOG_CAPTURED");result=0; }
    else fputs("ACM opened but t4_diag completion missing.\n",stderr);
done:
    if(claimed) libusb_release_interface(h,0);
    libusb_close(h);libusb_exit(ctx);return result;
}
