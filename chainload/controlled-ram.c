/* Host RAM transport only. No exploit, bootloader patches or storage commands.
 * Default requires an ALREADY controlled BootROM DFU. Recovery reuse is explicit.
 * The pinned, preexisting iBSS file is never generated or modified here.
 */
#include <libirecovery.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "inputs.h"

static irecv_client_t client;
static uint64_t ecid;
static void fail(const char *message) {
    fprintf(stderr, "%s\n", message);
    if (client) irecv_close(client);
    exit(2);
}
static void require(irecv_error_t e, const char *operation) {
    if (e != IRECV_E_SUCCESS) {
        fprintf(stderr, "%s: %s\n", operation, irecv_strerror(e));
        fail("RAM transport stopped; OpeniBoot execution unconfirmed.");
    }
}
static unsigned char *read_checked(const char *path, size_t size, uint32_t crc) {
    FILE *f = fopen(path, "rb");
    unsigned char *data = malloc(size);
    if (!f || !data) fail("Cannot read pinned input.");
    if (fread(data, 1, size, f) != size || fgetc(f) != EOF)
        fail("Pinned input length changed; nothing sent.");
    fclose(f);
    uint32_t sum = ~0U;
    for (size_t i = 0; i < size; i++) {
        sum ^= data[i];
        for (int bit = 0; bit < 8; bit++)
            sum = (sum >> 1) ^ (0xedb88320U & (0U - (sum & 1U)));
    }
    if (~sum != crc) fail("Pinned input CRC changed; nothing sent.");
    return data;
}
static int connect_target(void) {
    require(irecv_open_with_ecid_and_attempts(&client, ecid, 3), "connect");
    const struct irecv_device_info *d = irecv_get_device_info(client);
    if (!d || d->cpid != 0x8930 || d->bdid != 8 || d->ecid != ecid)
        fail("Expected this project's N81AP; nothing sent.");
    int mode;
    require(irecv_get_mode(client, &mode), "mode");
    return mode;
}
static int recovery(int mode) {
    return mode >= IRECV_K_RECOVERY_MODE_1 && mode <= IRECV_K_RECOVERY_MODE_4;
}
int main(int argc, char **argv) {
    if (argc != 5) {
        fprintf(stderr, "Usage: %s ECID existing-iBSS.dfu fixture.bin controlled-dfu|controlled-ibss\n", argv[0]);
        return 2;
    }
    char *end;
    ecid = strtoull(argv[1], &end, 0);
    if (!ecid || *end) fail("Invalid ECID.");
    int reuse = !strcmp(argv[4], "controlled-ibss");
    if (!reuse && strcmp(argv[4], "controlled-dfu")) fail("Invalid controlled context.");
    /* Hashes are also checked by run.py; CRC checks the actual in-memory bytes. */
    unsigned char *ibss = read_checked(argv[2], IBSS_SIZE, IBSS_CRC);
    unsigned char *image = read_checked(argv[3], FIXTURE_SIZE, FIXTURE_CRC);
    int mode = connect_target();
    if (!reuse) {
        const struct irecv_device_info *d = irecv_get_device_info(client);
        if (mode != IRECV_K_DFU_MODE || !d->srtg || strcmp(d->srtg, "iBoot-574.4") ||
            !d->serial_string || !strstr(d->serial_string, "PWND:["))
            fail("Already controlled N81 DFU required. No exploit is invoked; nothing sent.");
        puts("Existing controlled DFU verified; uploading UNCHANGED pinned iBSS to RAM.");
        fflush(stdout);
        require(irecv_send_buffer(client, ibss, IBSS_SIZE, IRECV_SEND_OPT_DFU_NOTIFY_FINISH), "existing iBSS RAM upload");
        irecv_close(client); client = NULL;
        sleep(2);
        mode = connect_target();
    }
    if (!recovery(mode)) fail("Controlled iBSS Recovery required; no fixture sent.");
    puts("Uploading RAM placement fixture at 0x41000000; native image and loader remain RAM-only.");
    fflush(stdout);
    require(irecv_send_buffer(client, image, FIXTURE_SIZE, IRECV_SEND_OPT_NONE), "fixture RAM upload");
    unsigned char command[] = "go";
    int n = irecv_usb_control_transfer(client, 0x40, 0, 0, 0, command, sizeof(command), 1000);
    printf("Existing go returned %d; upload status alone is NOT boot success.\n", n);
    irecv_close(client);
    free(ibss); free(image);
    return 0;
}
