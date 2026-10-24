/* Offline c5cee8c receiver model: deferred/split ACKs, packet loss, USB
 * re-enumeration and exact RAM reconstruction. No physical USB is linked. */
#include <time.h>
#include <unistd.h>
static time_t simulated_clock(time_t *p) {
    static time_t now;
    if(p)*p=now;
    return now++;
}
static int simulated_sleep(useconds_t n) {(void)n;return 0;}
#define time simulated_clock
#define usleep simulated_sleep
#define main linux_usb_main
#include "usb.c"
#undef main
#undef time
#undef usleep
#include <assert.h>

static unsigned char *payloads[3],*ram[3];
static long lengths[3],left,write_offset;
static unsigned bases[]={0x42000000,0x44800000,0x44000000};
static unsigned last_end;
static int file_index,files,jumps,versions,padded_packets,resets,failed_once,reset_issued;
static int ack_pending,initial_version=1,timeout_next,body_lost;
static unsigned long stage_entry,boot_entry;
static const char *scenario;
static char queued[4096];
static int is(const char *s) {return !strcmp(scenario,s);}

int libusb_init(libusb_context **c) {*c=(libusb_context *)1;return 0;}
void libusb_exit(libusb_context *c) {(void)c;}
libusb_device_handle *libusb_open_device_with_vid_pid(libusb_context *c,uint16_t vid,uint16_t pid)
{(void)c;assert(vid==0x525 && pid==0x1280);return (libusb_device_handle *)1;}
int libusb_claim_interface(libusb_device_handle *d,int n) {(void)d;assert(n==0);return 0;}
int libusb_release_interface(libusb_device_handle *d,int n) {(void)d;(void)n;return 0;}
void libusb_close(libusb_device_handle *d) {(void)d;}
const char *libusb_error_name(int e) {return e==LIBUSB_ERROR_TIMEOUT ? "SIM_TIMEOUT" : "SIM_IO";}
int libusb_reset_device(libusb_device_handle *d) {
    (void)d;resets++;assert(resets<=2 && !jumps);
    if(is("reset-fail"))return LIBUSB_ERROR_IO;
    /* USB reset clears only transfer state; RAM survives, as in resetUSB
     * and acm_started. A fresh version must precede all resumed data. */
    queued[0]=0;left=ack_pending=body_lost=0;reset_issued=1;
    return 0;
}

int libusb_bulk_transfer(libusb_device_handle *d,unsigned char endpoint,
                        unsigned char *data,int size,int *done,unsigned timeout)
{
    (void)d;(void)timeout;*done=0;
    if(endpoint==0x81) {
        if(timeout_next) {timeout_next=0;return LIBUSB_ERROR_TIMEOUT;}
        if(!queued[0])return LIBUSB_ERROR_TIMEOUT;
        int n=(int)strlen(queued);if(n>61)n=61;if(n>size)n=size;
        memcpy(data,queued,(size_t)n);memmove(queued,queued+n,strlen(queued+n)+1);
        *done=n;return 0;
    }
    assert(endpoint==2);*done=size;
    if(left) {
        assert(!reset_issued && size==512);
        int copy=left<size ? (int)left : size;
        if(is("recover-out") && file_index==1 && write_offset==2*1024*1024+512 && !failed_once) {
            copy=256;failed_once=body_lost=1;*done=256;
        }
        assert(!memcmp(data,payloads[file_index]+write_offset,(size_t)copy));
        memcpy(ram[file_index]+write_offset,data,(size_t)copy);
        if(!body_lost) {
            for(int i=copy;i<size;i++)assert(data[i]==0);
            if(copy<size)padded_packets++;
        }
        write_offset+=copy;left-=copy;
        if(body_lost)return LIBUSB_ERROR_TIMEOUT;
        if(!left) {ack_pending=1;last_end=bases[file_index]+(unsigned)write_offset;}
        return 0;
    }
    char line[256];assert(size<(int)sizeof(line));memcpy(line,data,(size_t)size);line[size]=0;
    if(!strcmp(line,"version\n")) {
        versions++;
        const char *version="openiboot 0.3 commit c5cee8c for iPod Touch 4G\n";
        if((initial_version && is("bad-version")) || (reset_issued && is("fresh-version-fail")))version="WRONG VERSION\n";
        initial_version=reset_issued=0;
        if(ack_pending) {
            if(is("timeout") || is("reset-fail") || is("fresh-version-fail") ||
               (is("recover-ack") && file_index==1 && write_offset==3*1024*1024 && !failed_once)) {
                queued[0]=0;failed_once=1;return 0;
            }
            if(is("missing-ack"))snprintf(queued,sizeof(queued),"%sACM: Done: version.",version);
            else snprintf(queued,sizeof(queued),"ACM: Received file (finished at 0x%08x)!\n%sACM: Done: version.",
                          last_end+(is("wrong-end") ? 1 : 0),version);
            ack_pending=0;
        } else snprintf(queued,sizeof(queued),"%sACM: Done: version.",version);
        timeout_next=1;
    } else if(!strncmp(line,"sendfile ",9)) {
        unsigned a;long n;assert(sscanf(line,"sendfile %x %ld",&a,&n)==2);
        assert(!reset_issued && !ack_pending && !queued[0]);
        file_index=-1;
        for(int i=0;i<3;i++)if(a>=bases[i] && a<bases[i]+lengths[i])file_index=i;
        assert(file_index>=0);write_offset=a-bases[file_index];
        long expected=lengths[file_index]-write_offset;
        if(expected>1024*1024)expected=1024*1024;
        assert(n==expected && n>0);files++;left=n;
    } else if(!strncmp(line,"jump ",5)) {
        unsigned long a;assert(sscanf(line,"jump %lx",&a)==1);jumps++;
        assert(!ack_pending && !reset_issued && !left);
        for(int i=0;i<3;i++)assert(!memcmp(ram[i],payloads[i],(size_t)lengths[i]));
        if(a==0x684) {assert(jumps==1);strcpy(queued,"ACM: Done: jump 0x684.");}
        else if(a==stage_entry) {
            assert(jumps==2);
            if(is("bad-stage"))strcpy(queued,"[T4_LINUX] REFUSED: checksum\n");
            else snprintf(queued,sizeof(queued),
                "[T4_LINUX] inherited framebuffer=48104580; machine_id=3564; RAM_ONLY\n"
                "[T4_LINUX] prepared cmdline: console=t4fb0 loglevel=8 ignore_loglevel "
                "t4fb=0x%08x t4_test=" T4_TEST_NAME "\nT4_LINUX_STAGED_NOT_EXECUTED\n",
                is("bad-cmdline") ? 0 : 0x08104580);
        } else {assert(a==boot_entry && jumps==3);return 0;}
    } else {fprintf(stderr,"Unexpected command %s",line);abort();}
    return 0;
}

int main(int argc,char **argv)
{
    assert(argc==8);scenario=argv[7];
    stage_entry=strtoul(argv[5],NULL,0);boot_entry=strtoul(argv[6],NULL,0);
    for(int i=0;i<3;i++) {
        FILE *f=fopen(argv[i+2],"rb");assert(f);assert(!fseek(f,0,SEEK_END));
        lengths[i]=ftell(f);assert(lengths[i]>0);rewind(f);
        payloads[i]=malloc((size_t)lengths[i]);ram[i]=malloc((size_t)lengths[i]);assert(payloads[i] && ram[i]);
        memset(ram[i],0xcc,(size_t)lengths[i]);
        assert(fread(payloads[i],1,(size_t)lengths[i],f)==(size_t)lengths[i]);fclose(f);
    }
    int result=linux_usb_main(7,argv);
    if(is("bad-version"))assert(result==3 && files==0 && jumps==0 && resets==0);
    else if(is("reset-fail") || is("fresh-version-fail"))assert(result==3 && files==1 && jumps==0 && resets==1);
    else if(is("missing-ack") || is("wrong-end") || is("timeout"))assert(result==3 && files==3 && jumps==0 && resets==2);
    else if(is("bad-stage") || is("bad-cmdline"))assert(result==4 && files==7 && jumps==2 && resets==0);
    else {
        int recovered=is("recover-ack") || is("recover-out");
        assert(result==0 && jumps==(!strcmp(argv[1],"--boot")?3:2));
        assert(files==7+recovered && resets==recovered && padded_packets==3);
        for(int i=0;i<3;i++)assert(!memcmp(ram[i],payloads[i],(size_t)lengths[i]));
    }
    for(int i=0;i<3;i++) {free(payloads[i]);free(ram[i]);}
    printf("OFFLINE_UPLOAD_V2_PASS %s\n",scenario);return 0;
}
