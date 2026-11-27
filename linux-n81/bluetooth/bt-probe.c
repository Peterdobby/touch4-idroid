// SPDX-License-Identifier: GPL-2.0
/*
 * Ask the BCM4329 Bluetooth controller who it is, over UART1 by polling
 * (no kernel driver yet). Takes it out of reset, sends HCI Reset, Read Local
 * Version and Read BD_ADDR at 115200 8N1, prints the events, and puts it back
 * into reset.
 */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#define ULCON	0x00
#define UCON	0x04
#define UFCON	0x08
#define UMCON	0x0c
#define UTRSTAT	0x10
#define UERSTAT	0x14
#define UFSTAT	0x18
#define UMSTAT	0x1c
#define UTXH	0x20
#define URXH	0x24
#define UBRDIV	0x28

#define PIN_BT_WAKE	7
#define PIN_BT_RESET	8
#define PIN_RTS		56

static volatile uint32_t *uart, *gpio;
#define U(o) uart[(o) / 4]

static double now(void)
{
	struct timespec t;

	clock_gettime(CLOCK_MONOTONIC, &t);
	return t.tv_sec + t.tv_nsec / 1e9;
}

static int rx_ready(void)
{
	return U(UFSTAT) & 0x1ff;	/* FIFO count or full */
}

static void command(const char *name, const uint8_t *cmd, int len)
{
	double end;
	int got = 0;

	while (rx_ready())
		(void)U(URXH);
	for (int i = 0; i < len; i++) {
		end = now() + 0.5;
		while (!(U(UTRSTAT) & 2))
			if (now() > end) {
				printf("%s: transmitter stuck (CTS %08x)\n", name, U(UMSTAT));
				return;
			}
		U(UTXH) = cmd[i];
	}
	printf("%s ->", name);
	for (end = now() + 0.6; now() < end;)
		if (rx_ready()) {
			printf(" %02x", U(URXH) & 0xff);
			got++;
			end = now() + 0.1;
		}
	printf(got ? "  (errors %x)\n" : " no answer (errors %x)\n", U(UERSTAT));
}

int main(int argc, char **argv)
{
	static const uint8_t reset[] = { 0x01, 0x03, 0x0c, 0x00 };
	static const uint8_t version[] = { 0x01, 0x01, 0x10, 0x00 };
	static const uint8_t bdaddr[] = { 0x01, 0x09, 0x10, 0x00 };
	int fd = open("/dev/mem", O_RDWR | O_SYNC);
	void *u = mmap(0, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0x82600000);
	void *g = mmap(0, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0xbfa00000);
	uint32_t wake, rst, rts;

	if (u == MAP_FAILED || g == MAP_FAILED)
		return 2;
	uart = u;
	gpio = g;
	printf("before: ulcon %x ucon %x ufcon %x umcon %x ubrdiv %x umstat %x\n",
	       U(ULCON), U(UCON), U(UFCON), U(UMCON), U(UBRDIV), U(UMSTAT));
	wake = gpio[PIN_BT_WAKE];
	rst = gpio[PIN_BT_RESET];
	rts = gpio[PIN_RTS];

	U(ULCON) = 3;			/* 8N1 */
	/* bt-probe [UCON [UBRDIV]] */
	U(UCON) = argc > 1 ? strtoul(argv[1], 0, 0) : 0x405;
	U(UFCON) = 7;			/* FIFOs on and cleared */
	U(UBRDIV) = argc > 2 ? strtoul(argv[2], 0, 0) : 12;	/* 24 MHz/16/13 */
	(void)U(UERSTAT);
	U(0x2c) = 0;
	gpio[PIN_RTS] = 0x212;		/* drive RTS low: the host is ready */

	gpio[PIN_BT_RESET] = 0x212;
	usleep(100000);
	gpio[PIN_BT_WAKE] = 0x213;
	gpio[PIN_BT_RESET] = 0x213;
	usleep(300000);
	printf("after reset: umstat %x ufstat %x\n", U(UMSTAT), U(UFSTAT));

	command("HCI_Reset", reset, sizeof(reset));
	command("Read_Local_Version", version, sizeof(version));
	command("Read_BD_ADDR", bdaddr, sizeof(bdaddr));

	gpio[PIN_BT_RESET] = rst;
	gpio[PIN_BT_WAKE] = wake;
	gpio[PIN_RTS] = rts;
	return 0;
}
