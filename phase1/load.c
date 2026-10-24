/* N81AP, exact offline-patched 4.1 iBSS -> RAM image. No storage commands. */
#include <libirecovery.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static irecv_client_t client;
static uint64_t ecid;
static int native_image_valid(const char *path) {
    static const unsigned char code[] = {
        0x00,0x00,0xa0,0xe3,0x08,0x10,0x9f,0xe5,
        0x00,0x20,0xa0,0xe3,0x04,0x30,0x9f,0xe5,
        0x13,0xff,0x2f,0xe1,0x00,0x10,0x00,0x41,
        0x6d,0x49,0x01,0x84
    };
    static const unsigned char nop[] = {0x00,0xf0,0x20,0xe3};
    unsigned char header[0x1000];
    FILE *f = fopen(path, "rb");
    if(!f) return 0;
    int valid = fread(header, 1, sizeof(header), f) == sizeof(header);
    valid = valid && !memcmp(header, code, sizeof(code));
    for(size_t i=sizeof(code); valid && i<sizeof(header); ++i) {
        unsigned char expected = i<0x40 ? nop[(i-sizeof(code))%4] : 0;
        if(header[i] != expected) valid = 0;
    }
    if(fseek(f, 0, SEEK_END)) valid = 0;
    long size = ftell(f);
    if(size <= 0x1000 || size > 0x1000000 || size%0x1000) valid = 0;
    fclose(f);
    return valid;
}
static void require(irecv_error_t e, const char *what) {
    if(e != IRECV_E_SUCCESS) {
        fprintf(stderr, "%s: %s\n", what, irecv_strerror(e));
        if(client) irecv_close(client);
        exit(1);
    }
}
static void connect_target(void) {
    require(irecv_open_with_ecid_and_attempts(&client, ecid, 3), "connect");
    const struct irecv_device_info *d = irecv_get_device_info(client);
    if(!d || d->cpid != 0x8930 || d->bdid != 8 || d->ecid != ecid) {
        fputs("Wrong target; nothing sent.\n", stderr);
        exit(2);
    }
}
int main(int argc, char **argv) {
    if(argc != 4) { fprintf(stderr,"Usage: %s ECID patched-iBSS.dfu native-image.bin\n",argv[0]); return 2; }
    if(!native_image_valid(argv[3])) {
        fputs("Native wrapped image required; raw payload refused before USB access.\n", stderr);
        return 2;
    }
    char *end;
    ecid = strtoull(argv[1], &end, 0);
    if(!ecid || *end) return 2;
    connect_target();
    int mode;
    require(irecv_get_mode(client, &mode), "mode");
    const struct irecv_device_info *d = irecv_get_device_info(client);
    if(mode != IRECV_K_DFU_MODE || !d->srtg || strcmp(d->srtg,"iBoot-574.4") ||
       !d->serial_string || !strstr(d->serial_string,"PWND:[")) {
        fputs("Expected pwned BootROM DFU; nothing sent.\n", stderr); return 3;
    }
    puts("Pwned N81AP verified. Uploading patched iBSS to RAM."); fflush(stdout);
    require(irecv_send_file(client, argv[2], IRECV_SEND_OPT_DFU_NOTIFY_FINISH), "iBSS upload");
    irecv_close(client); client = NULL;
    sleep(2);
    connect_target();
    require(irecv_get_mode(client, &mode), "iBSS mode");
    if(mode < IRECV_K_RECOVERY_MODE_1 || mode > IRECV_K_RECOVERY_MODE_4) {
        fputs("iBSS Recovery not observed; stopped.\n",stderr); return 4;
    }
    puts("iBSS Recovery verified. Uploading RAM image at 0x41000000."); fflush(stdout);
    require(irecv_send_file(client, argv[3], IRECV_SEND_OPT_NONE), "RAM upload");
    unsigned char command[] = "go";
    int n = irecv_usb_control_transfer(client, 0x40, 0, 0, 0, command, sizeof(command), 1000);
    printf("go transfer returned %d; execution must be checked independently.\n",n);
    irecv_close(client);
    /* The jump tears down USB and can cause an otherwise expected timeout.
     * This exit status means only that both uploads completed. */
    return 0;
}
