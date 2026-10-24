/* Host control-flow test. All USB and sleep functions are replaced below. */
#include <assert.h>
#define main loader_main
#include "../load_ram.c"
#undef main

static int commands, uploads, failure_stage, refusal;
static irecv_event_cb_t receiver;
static struct irecv_device_info fake_info = {
    .cpid = 0x8930, .bdid = 8, .ecid = 1,
    .srtg = "iBoot-574.4", .serial_string = "PWND:mock"
};
irecv_error_t irecv_open_with_ecid_and_attempts(irecv_client_t *c, uint64_t e, int a)
{ (void)a; assert(e == 1); *c = (irecv_client_t)1; return 0; }
const struct irecv_device_info *irecv_get_device_info(irecv_client_t c)
{ (void)c; return &fake_info; }
irecv_error_t irecv_event_subscribe(irecv_client_t c, irecv_event_type t, irecv_event_cb_t cb, void *u)
{ (void)c; (void)t; (void)u; receiver = cb; return 0; }
irecv_error_t irecv_get_mode(irecv_client_t c, int *mode)
{ (void)c; *mode = uploads ? IRECV_K_RECOVERY_MODE_1 : IRECV_K_DFU_MODE; return 0; }
irecv_error_t irecv_send_file(irecv_client_t c, const char *f, unsigned int o)
{ (void)c; (void)f; (void)o; uploads++; return 0; }
irecv_error_t irecv_close(irecv_client_t c) { (void)c; return 0; }
const char *irecv_strerror(irecv_error_t e) { (void)e; return "mock"; }
unsigned int sleep(unsigned int s) { (void)s; return 0; }
int irecv_usb_control_transfer(irecv_client_t c, uint8_t a, uint8_t b, uint16_t d,
    uint16_t e, unsigned char *data, uint16_t length, unsigned int timeout)
{
    (void)c; (void)a; (void)b; (void)d; (void)e; (void)timeout;
    assert(length == 3 && !strcmp((char *)data, "go"));
    commands++;
    return commands == failure_stage && !refusal ? -11 : length;
}
irecv_error_t irecv_receive(irecv_client_t c)
{
    if (!commands) return 0;
    const char *markers[] = {"OIB_STATE_OK", "OIB_MAP_OK", "OIB_SELECT_OK", "OIB_L1_OK", "OIB_L2_OK", "OIB_IRQ_OK", "OIB_CACHE_OK", "OIB_CPU_OK"};
    const char *reply = commands == failure_stage ?
        (refusal == 1 ? "OIB_HANDOFF_REFUSED" : refusal == 2 ? "\xa9\x00\xff" : "") : markers[commands - 1];
    irecv_event_t event = {.type = IRECV_RECEIVED, .data = reply, .size = (int)strlen(reply)};
    if (commands == failure_stage && refusal == 2) event.size = 3;
    receiver(c, &event);
    return 0;
}
int main(int argc, char **argv)
{
    assert(argc == 3);
    failure_stage = atoi(argv[1]); refusal = atoi(argv[2]);
    char *args[] = {"mock", "1", "mock-ibss", "mock-image", "--diagnose"};
    int result = loader_main(5, args);
    assert(result == (failure_stage ? refusal == 1 ? 7 : 8 : 0));
    assert(commands == (failure_stage ? failure_stage : 8));
    assert(uploads == 2);
    return 0;
}
