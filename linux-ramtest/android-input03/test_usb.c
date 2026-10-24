/* Offline transport simulation. No real libusb implementation is linked. */
#define main linux_usb_main
#include "usb.c"
#undef main
#include <assert.h>

static char queued[1024];
static long remaining;
static int files,jumps,versions;
static unsigned long stage_entry,boot_entry;
static int bad_version,bad_stage,bad_cmdline;

int libusb_init(libusb_context **ctx) {*ctx=(libusb_context *)1;return 0;}
void libusb_exit(libusb_context *ctx) {(void)ctx;}
libusb_device_handle *libusb_open_device_with_vid_pid(libusb_context *ctx,uint16_t vid,uint16_t pid)
{(void)ctx;assert(vid==0x525 && pid==0x1280);return (libusb_device_handle *)1;}
int libusb_claim_interface(libusb_device_handle *dev,int n) {(void)dev;assert(n==0);return 0;}
int libusb_release_interface(libusb_device_handle *dev,int n) {(void)dev;(void)n;return 0;}
void libusb_close(libusb_device_handle *dev) {(void)dev;}
const char *libusb_error_name(int code) {(void)code;return "OFFLINE_SIMULATION";}
int libusb_bulk_transfer(libusb_device_handle *dev,unsigned char endpoint,
                        unsigned char *data,int size,int *done,unsigned timeout)
{
    (void)dev;(void)timeout;
    if(endpoint==0x81) {
        if(!queued[0]) {*done=0;return LIBUSB_ERROR_IO;}
        int n=(int)strlen(queued);if(n>size)n=size;
        memcpy(data,queued,(size_t)n);memmove(queued,queued+n,strlen(queued+n)+1);
        *done=n;return 0;
    }
    assert(endpoint==2);*done=size;
    if(remaining) {assert(size<=remaining);remaining-=size;return 0;}
    char line[256];assert(size<(int)sizeof(line));memcpy(line,data,(size_t)size);line[size]=0;
    if(!strcmp(line,"version\n")) {
        versions++;
        snprintf(queued,sizeof(queued),"%s%sACM: Done: version.",
            files ? "ACM: Received file (finished)!\n" : "",
            bad_version ? "WRONG VERSION\n" : "openiboot 0.3 commit c5cee8c for iPod Touch 4G\n");
    } else if(!strncmp(line,"sendfile ",9)) {
        unsigned a;long n;assert(sscanf(line,"sendfile %x %ld",&a,&n)==2);
        unsigned addresses[]={0x42000000,0x44800000,0x44000000};
        assert(files<3 && a==addresses[files] && n>0);files++;remaining=n;
    } else if(!strncmp(line,"jump ",5)) {
        unsigned long a;assert(sscanf(line,"jump %lx",&a)==1);jumps++;
        if(a==0x684) {assert(files==3);strcpy(queued,"ACM: Done: jump 0x684.");}
        else if(a==stage_entry) {
            assert(jumps==2);
            snprintf(queued,sizeof(queued),"%s\nACM: Done: jump 0x%lx.",
                bad_stage ? "[T4_LINUX] REFUSED: checksum" :
                "[T4_LINUX] inherited framebuffer=48104580; machine_id=3564; RAM_ONLY\n"
                "[T4_LINUX] prepared cmdline: console=t4fb0 loglevel=8 ignore_loglevel rdinit=/init panic=0 t4fb=0x08104580 t4_test=" T4_TEST_NAME "\n"
                "T4_LINUX_STAGED_NOT_EXECUTED",a);
            if(bad_cmdline) snprintf(queued,sizeof(queued),
                "[T4_LINUX] inherited framebuffer=48104580; machine_id=3564; RAM_ONLY\n"
                "[T4_LINUX] prepared cmdline: console=t4fb0 l081045808 ignore_loglevel "
                "rdinit=/init panic=0 t4fb=0x00000000 t4_test=" T4_TEST_NAME "\n"
                "T4_LINUX_STAGED_NOT_EXECUTED\nACM: Done: jump 0x%lx.",a);
        } else {assert(a==boot_entry && jumps==3 && versions==5);}
    } else {fprintf(stderr,"Unexpected command %s",line);abort();}
    return 0;
}
int main(int argc,char **argv)
{
    assert(argc==8);
    bad_version=!strcmp(argv[7],"bad-version");bad_stage=!strcmp(argv[7],"bad-stage");
    bad_cmdline=!strcmp(argv[7],"bad-cmdline");
    stage_entry=strtoul(argv[5],NULL,0);boot_entry=strtoul(argv[6],NULL,0);
    int result=linux_usb_main(7,argv);
    if(bad_version)assert(result==3 && files==0 && jumps==0);
    else if(bad_stage || bad_cmdline)assert(result==4 && files==3 && jumps==2);
    else {assert(result==0 && files==3 && jumps==(!strcmp(argv[1],"--boot")?3:2));}
    puts("OFFLINE_PROTOCOL_TEST_PASSED");
    return 0;
}
