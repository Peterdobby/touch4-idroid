/* One-shot client for the CURRENT acm/ protocol, not the older oibc protocol.
 * Only sends the read-only command "help"; success requires its completion. */
#include <libusb.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

int main(void) {
    libusb_context *ctx = NULL;
    if(libusb_init(&ctx)) return 1;
    libusb_device_handle *h = NULL;
    time_t end = time(NULL)+20;
    while(time(NULL)<end && !h) {
        h = libusb_open_device_with_vid_pid(ctx,0x0525,0x1280);
        if(!h) usleep(250000);
    }
    if(!h) { fputs("No OpeniBoot USB 0525:1280 observed. Boot unconfirmed.\n",stderr); libusb_exit(ctx); return 2; }
    puts("OpeniBoot USB 0525:1280 opened.");
    int result = 3, claimed = 0, config = 0;
    char data[65536]; size_t used = 0;
    int n, e;
    e = libusb_get_configuration(h,&config);
    if(e) goto done;
    if(config != 1 && libusb_set_configuration(h,1)) goto done;
    e = libusb_claim_interface(h,0);
    if(e) { fprintf(stderr,"claim: %s\n",libusb_error_name(e)); goto done; }
    claimed = 1;
    unsigned char help[] = "version\n";
    e = libusb_bulk_transfer(h,0x02,help,sizeof(help)-1,&n,2000);
    if(e || n != (int)sizeof(help)-1) { fprintf(stderr,"send help: %s\n",libusb_error_name(e)); goto done; }
    end = time(NULL)+12;
    while(time(NULL)<end && used+512+1 < sizeof(data)) {
        n = 0;
        e = libusb_bulk_transfer(h,0x81,(unsigned char*)data+used,512,&n,500);
        if(n>0) { fwrite(data+used,1,(size_t)n,stdout); fflush(stdout); used+=(size_t)n; data[used]=0; }
        if(used && strstr(data,"ACM: Done: images_list.")) { result=0; break; }
        if(e && e != LIBUSB_ERROR_TIMEOUT) { fprintf(stderr,"read: %s\n",libusb_error_name(e)); break; }
    }
    if(!result) puts("\nOPENIBOOT_VERSION_CONFIRMED");
    else fputs("USB identity observed, but version round-trip unconfirmed.\n",stderr);
done:
    if(claimed) libusb_release_interface(h,0);
    libusb_close(h); libusb_exit(ctx);
    return result;
}
