/* Read-only, fresh version round trip on the existing OpeniBoot ACM protocol. */
#include <libusb.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

int main(int argc, char **argv) {
    libusb_context *ctx = NULL;
    if (libusb_init(&ctx)) return 1;
    libusb_device_handle *h = NULL;
    if (argc == 2 && !strcmp(argv[1], "--absent")) {
        h = libusb_open_device_with_vid_pid(ctx, 0x0525, 0x1280);
        int result = h ? 1 : 0;
        if (h) libusb_close(h);
        libusb_exit(ctx);
        return result;
    }
    time_t end = time(NULL) + 20;
    while (time(NULL) < end && !h) {
        h = libusb_open_device_with_vid_pid(ctx, 0x0525, 0x1280);
        if (!h) usleep(250000);
    }
    if (!h) {
        fputs("No OpeniBoot USB 0525:1280 observed; boot unconfirmed.\n", stderr);
        libusb_exit(ctx); return 2;
    }
    puts("OpeniBoot USB 0525:1280 opened.");
    int result = 3, claimed = 0, config = 0, n = 0, e;
    char data[131072]; size_t used = 0;
    data[0] = 0;
    if (libusb_get_configuration(h, &config)) goto done;
    if (config != 1 && libusb_set_configuration(h, 1)) goto done;
    e = libusb_claim_interface(h, 0);
    if (e) { fprintf(stderr, "claim: %s\n", libusb_error_name(e)); goto done; }
    claimed = 1;
    /* Drain old messages before asking a new question. */
    for (int i = 0; i < 8; i++) {
        unsigned char discard[512]; n = 0;
        e = libusb_bulk_transfer(h, 0x81, discard, sizeof(discard), &n, 50);
        if (e == LIBUSB_ERROR_TIMEOUT || n == 0) break;
        if (e) goto done;
    }
    unsigned char command[] = "version\n";
    e = libusb_bulk_transfer(h, 0x02, command, sizeof(command)-1, &n, 2000);
    if (e || n != sizeof(command)-1) goto done;
    end = time(NULL) + 12;
    while (time(NULL) < end && used + 513 < sizeof(data)) {
        n = 0;
        e = libusb_bulk_transfer(h, 0x81, (unsigned char *)data+used, 512, &n, 500);
        if (n > 0) {
            fwrite(data+used, 1, n, stdout); fflush(stdout);
            used += n; data[used] = 0;
        }
        char *start = strstr(data, "ACM: Starting version");
        char *version = start ? strstr(start, "openiboot 0.3 commit c5cee8c for iPod Touch 4G") : NULL;
        char *complete = version ? strstr(version, "ACM: Done: version.") : NULL;
        if (complete && (strstr(complete, "ACM: Done: version.\n") == complete ||
                         strstr(complete, "ACM: Done: version.\r\n") == complete)) {
            result = 0; break;
        }
        if (e && e != LIBUSB_ERROR_TIMEOUT) break;
    }
done:
    if (claimed) libusb_release_interface(h, 0);
    libusb_close(h); libusb_exit(ctx);
    if (!result) puts("\nCHAINLOAD_USB_VERSION_CONFIRMED");
    else fputs("Fresh ACM version round trip unconfirmed.\n", stderr);
    return result;
}
