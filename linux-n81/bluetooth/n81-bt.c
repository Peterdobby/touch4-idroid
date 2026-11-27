// SPDX-License-Identifier: GPL-2.0
/*
 * n81-bt up     power the BCM4329, attach it to the kernel (H4 on ttySAC1), bring
 *               up hci0 and stay in the background holding the line
 * n81-bt scan   list the discoverable devices nearby (names, partial addresses)
 * n81-bt visible  be discoverable as "iPod-Linux"
 */
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <termios.h>
#include <unistd.h>

#define AF_BT		31
#define BTPROTO_HCI	1
#define SOL_HCI		0
#define HCI_FILTER	2
#define N_HCI		15
#define HCIUARTSETPROTO	_IOW('U', 200, int)
#define HCIDEVUP	_IOW('H', 201, int)
#define HCIINQUIRY	_IOR('H', 240, int)
#define HCISETSCAN	_IOW('H', 221, int)

struct sockaddr_hci {
	unsigned short family, dev, channel;
};
struct hci_filter {
	uint32_t type_mask, event_mask[2];
	uint16_t opcode;
};
struct inquiry_info {
	uint8_t bdaddr[6], pscan_rep_mode, pscan_period_mode, pscan_mode, dev_class[3];
	uint16_t clock_offset;
} __attribute__((packed));

static int speed = 750000, flow = 1;	/* n81-bt up [SPEED [FLOW]] */

static void power(void)
{
	int fd = open("/dev/mem", O_RDWR | O_SYNC);
	volatile uint32_t *gpio = mmap(0, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0xbfa00000);

	if (gpio == MAP_FAILED)
		return;
	/* RTS from the UART (hardware flow control), or held low */
	gpio[56] = flow ? 0xa30 : 0x212;
	gpio[8] = 0x212;	/* reset */
	usleep(100000);
	gpio[7] = 0x213;	/* wake */
	gpio[8] = 0x213;
	usleep(300000);
	close(fd);
}

#define FIRMWARE "/lib/firmware/brcm/n81-bt.hcd"

/* Send one HCI command on the raw port and wait for its Command Complete. */
static int send_command(int tty, const uint8_t *cmd, int len)
{
	uint8_t pkt[260], ev[7];
	struct pollfd p = { .fd = tty, .events = POLLIN };
	int got = 0;

	pkt[0] = 0x01;
	memcpy(pkt + 1, cmd, len);
	if (write(tty, pkt, len + 1) != len + 1)
		return -1;
	/* 04 0e LEN 01 opcode status; skip anything before the 04 */
	while (got < 7 && poll(&p, 1, 1000) > 0) {
		if (read(tty, ev + got, 1) != 1)
			return -1;
		if (got || ev[0] == 0x04)
			got++;
	}
	if (got < 7 || ev[1] != 0x0e || ev[4] != cmd[0] || ev[5] != cmd[1] || ev[6])
		return -1;
	for (int rest = ev[2] - 4; rest > 0 && poll(&p, 1, 200) > 0; rest--)
		if (read(tty, pkt, 1) != 1)
			break;
	return 0;
}

/*
 * Patch RAM download, as every Broadcom controller takes it: reset, enter the
 * download mode, then the records of the .hcd file (the last one launches the
 * patched firmware). The file is this module's, from iOS's BlueTool.
 */
static int load_firmware(int tty)
{
	static const uint8_t reset[] = { 0x03, 0x0c, 0 }, download[] = { 0x2e, 0xfc, 0 };
	uint8_t cmd[3 + 255];
	FILE *f = fopen(FIRMWARE, "rb");
	int records = 0;

	if (!f) {
		puts("no firmware: using the chip's ROM");
		return 0;
	}
	if (send_command(tty, reset, 3) || send_command(tty, download, 3))
		goto fail;
	usleep(100000);
	while (fread(cmd, 1, 3, f) == 3) {
		if (fread(cmd + 3, 1, cmd[2], f) != cmd[2] || send_command(tty, cmd, 3 + cmd[2]))
			goto fail;
		records++;
	}
	fclose(f);
	usleep(300000);
	tcflush(tty, TCIFLUSH);
	if (send_command(tty, reset, 3)) {
		puts("chip did not come back after the firmware");
		return -1;
	}
	printf("firmware loaded (%d commands)\n", records);
	/* what BlueTool adds for this patch ("bcm -r"): Write RAM, one byte each */
	{
		static const uint8_t ram[][8] = {
			{ 0x4c, 0xfc, 5, 0xc9, 0x15, 0x08, 0x00, 0x04 },	/* 0x815c9 = 4 */
			{ 0x4c, 0xfc, 5, 0xcc, 0x15, 0x08, 0x00, 0x03 },	/* 0x815cc = 3 */
		};

		for (int i = 0; i < 2; i++)
			printf("setting %d: %s\n", i, send_command(tty, ram[i], 8) ? "failed" : "ok");
	}
	/* the device's own address, as BlueTool's "bcm -A": vendor command 0xfc01 */
	{
		uint8_t set[9] = { 0x01, 0xfc, 6 }, mac[6];
		FILE *a = fopen("/lib/firmware/brcm/n81-bt.addr", "rb");

		if (a && fread(mac, 1, 6, a) == 6) {
			for (int i = 0; i < 6; i++)
				set[3 + i] = mac[5 - i];
			printf("device address: %s\n",
			       send_command(tty, set, 9) ? "failed" : "ok");
		}
		if (a)
			fclose(a);
	}
	return 0;
fail:
	printf("firmware failed at command %d\n", records);
	fclose(f);
	return -1;
}

/*
 * A2DP needs more than 115200. Broadcom's "update UART baud rate" (0xfc18, as
 * in the kernel's hci_bcm) to 1.5 Mbit/s, exact from the 24 MHz clock, with
 * hardware flow control.
 */
/*
 * A device tree without clk_uart_baud0 makes the serial driver accept a rate
 * and leave the divisor alone, so a rate set here would outlive us: write it
 * for every rate we use.
 */
static void set_divisor(int rate)
{
	int mem = open("/dev/mem", O_RDWR | O_SYNC);
	volatile uint32_t *u = mmap(0, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, mem, 0x82600000);
	uint32_t div = (24000000 + 8 * rate) / (16 * rate) - 1;

	if (u != MAP_FAILED && (u[0x28 / 4] & 0xffff) != div)
		u[0x28 / 4] = (u[0x28 / 4] & ~0xffffu) | div;
	close(mem);
}

static int speed_up(int tty, struct termios *t)
{
	uint8_t cmd[] = { 0x18, 0xfc, 6, 0, 0, speed, speed >> 8, speed >> 16, speed >> 24 };
	static const uint8_t version[] = { 0x01, 0x10, 0 };

	if (send_command(tty, cmd, sizeof(cmd))) {
		puts("the chip refused the new speed");
		return -1;
	}
	usleep(100000);
	{
		/* any rate, through termios2/BOTHER: 750000 has no constant */
		struct { uint32_t i, o, c, l; uint8_t line, cc[19]; uint32_t ispeed, ospeed; } t2;

		if (ioctl(tty, _IOR('T', 0x2a, t2), &t2))
			return -1;
		t2.c &= ~(0x100fu | 0x100fu << 16);
		t2.c |= 0x1000;			/* BOTHER */
		t2.ispeed = t2.ospeed = speed;
		if (flow)
			t2.c |= CRTSCTS;
		if (ioctl(tty, _IOW('T', 0x2b, t2), &t2))
			return -1;
		if (ioctl(tty, _IOR('T', 0x2a, t2), &t2) == 0)
			printf("port: %u bit/s\n", t2.ospeed);
		(void)t;
	}
	set_divisor(speed);
	tcflush(tty, TCIOFLUSH);
	/* the version reply carries more than a bare status; only ask */
	if (send_command(tty, version, sizeof(version))) {
		printf("no answer at %d\n", speed);
		return -1;
	}
	printf("serial at %d bit/s, flow control %d\n", speed, flow);
	return 0;
}

static int hci_socket(void)
{
	return socket(AF_BT, SOCK_RAW, BTPROTO_HCI);
}

static int up(void)
{
	struct termios t;
	int tty, proto = 0 /* H4 */, ldisc = N_HCI, s, ready[2];
	char ok = 1;

	power();
	if (pipe(ready))
		return 1;
	if (fork()) {
		close(ready[1]);
		if (read(ready[0], &ok, 1) != 1)
			ok = 1;
		return ok;
	}
	setsid();
	tty = open("/dev/ttySAC1", O_RDWR | O_NOCTTY);
	if (tty < 0 || tcgetattr(tty, &t)) {
		perror("ttySAC1");
		_exit(1);
	}
	cfmakeraw(&t);
	t.c_cflag |= CLOCAL;
	t.c_cflag &= ~CRTSCTS;
	cfsetspeed(&t, B115200);
	tcsetattr(tty, TCSANOW, &t);
	set_divisor(115200);
	tcflush(tty, TCIOFLUSH);
	if (load_firmware(tty) || speed_up(tty, &t))
		_exit(1);
	fflush(stdout);
	if (ioctl(tty, TIOCSETD, &ldisc) || ioctl(tty, HCIUARTSETPROTO, proto)) {
		perror("line discipline");
		_exit(1);
	}
	usleep(500000);
	s = hci_socket();
	/* the kernel powers a new controller on by itself: "already" is success */
	if (s < 0 || (ioctl(s, HCIDEVUP, 0) && errno != EALREADY)) {
		perror("hci0");
		_exit(1);
	}
	close(s);
	puts("hci0 up");
	fflush(stdout);
	ok = 0;
	if (write(ready[1], &ok, 1) != 1)
		_exit(1);
	close(ready[1]);
	freopen("/dev/null", "r+", stdin);
	freopen("/dev/null", "w", stdout);
	freopen("/dev/null", "w", stderr);
	for (;;)
		pause();
}

/* Name the controller and let others find and reach it. */
static int visible(void)
{
	static const char name[] = "iPod-Linux";
	uint8_t cmd[4 + 248] = { 0x01, 0x13, 0x0c, 248 };
	struct {
		uint16_t dev_id;
		uint32_t dev_opt;
	} scan = { 0, 3 /* inquiry and page scan */ };
	struct sockaddr_hci a = { AF_BT, 0, 0 };
	int s = hci_socket();

	memcpy(cmd + 4, name, sizeof(name));
	if (s < 0 || bind(s, (struct sockaddr *)&a, sizeof(a)) ||
	    write(s, cmd, sizeof(cmd)) != sizeof(cmd) || ioctl(s, HCISETSCAN, &scan)) {
		perror("visible");
		return 1;
	}
	printf("visible as %s\n", name);
	close(s);
	return 0;
}

/* Ask one device for its name; leaves name empty on timeout. */
static void remote_name(int s, const struct inquiry_info *d, char *name)
{
	uint8_t cmd[4 + 10] = { 0x01, 0x19, 0x04, 10 }, ev[260];
	struct pollfd p = { .fd = s, .events = POLLIN };

	name[0] = 0;
	memcpy(cmd + 4, d->bdaddr, 6);
	cmd[10] = d->pscan_rep_mode;
	cmd[12] = d->clock_offset & 0xff;
	cmd[13] = (d->clock_offset >> 8) | 0x80;
	if (write(s, cmd, sizeof(cmd)) != sizeof(cmd))
		return;
	while (poll(&p, 1, 6000) > 0) {
		int n = read(s, ev, sizeof(ev));

		/* packet type, event 0x07, length, status, address, name */
		if (n >= 10 && ev[1] == 0x07 && !memcmp(ev + 4, d->bdaddr, 6)) {
			if (!ev[3]) {
				int len = n - 10 < 63 ? n - 10 : 63;

				memcpy(name, ev + 10, len);
				name[len] = 0;
			}
			return;
		}
	}
}

static int scan(void)
{
	static struct {
		struct {
			uint16_t dev_id, flags;
			uint8_t lap[3], length, num_rsp;
		} req;
		struct inquiry_info info[16];
	} q = { .req = { 0, 1 /* flush */, { 0x33, 0x8b, 0x9e }, 8, 16 } };
	struct hci_filter f = { .type_mask = 1 << 4, .event_mask = { 1 << 7, 0 } };
	struct sockaddr_hci a = { AF_BT, 0, 0 };
	int s = hci_socket();

	if (s < 0 || ioctl(s, HCIINQUIRY, &q)) {
		perror("scan");
		return 1;
	}
	printf("%d device(s)\n", q.req.num_rsp);
	if (setsockopt(s, SOL_HCI, HCI_FILTER, &f, sizeof(f)) ||
	    bind(s, (struct sockaddr *)&a, sizeof(a))) {
		perror("hci");
		return 1;
	}
	for (int i = 0; i < q.req.num_rsp; i++) {
		char name[64];

		remote_name(s, &q.info[i], name);
		printf("  ..:%02x:%02x  %s\n", q.info[i].bdaddr[1], q.info[i].bdaddr[0],
		       name[0] ? name : "(no name)");
		fflush(stdout);
	}
	return 0;
}

int main(int argc, char **argv)
{
	setvbuf(stdout, NULL, _IONBF, 0);
	if (argc >= 2 && !strcmp(argv[1], "up")) {
		if (argc > 2)
			speed = atoi(argv[2]);
		if (argc > 3)
			flow = atoi(argv[3]);
		return up();
	}
	if (argc == 2 && !strcmp(argv[1], "scan"))
		return scan();
	if (argc == 2 && !strcmp(argv[1], "visible"))
		return visible();
	fprintf(stderr, "usage: n81-bt up|scan|visible\n");
	return 2;
}
