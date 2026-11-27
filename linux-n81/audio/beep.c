// SPDX-License-Identifier: GPL-2.0
/*
 * Speaker test: quiet square wave by PIO. n81-tone HZ [SECONDS]
 *
 * The codec (CS42L59, I2C 0x4a) is the I2S clock master. Register values and
 * their order are the writes iOS 6.1.6 for n81ap makes, recorded by running it
 * under qemu-ios with register tracing: start-up first, then playback. The SoC
 * port needs +0x410 = 0x28000300, which provides the codec's master clock; no
 * PMGR NCO is involved. Everything is switched off afterwards.
 */
#include <fcntl.h>
#include <linux/i2c-dev.h>
#include <linux/i2c.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#define AMPLITUDE 3000		/* of 32767 */
#define SPEAKER_PIN 161		/* 0x203 while playing, 0x202 otherwise */
#define RATE 44100		/* codec register 0x0a = 0x0b */

static const uint8_t startup[][2] = {
	{0x3b, 0xa5}, {0x3b, 0x00}, {0x07, 0x00}, {0x09, 0x20}, {0x09, 0x20},
	{0x0a, 0x0b}, {0x31, 0x80}, {0x1a, 0x00}, {0x0e, 0xc0}, {0x0e, 0xc8},
	{0x32, 0x8f}, {0x0c, 0xc0}, {0x1a, 0x01}, {0x10, 0x01}, {0x0e, 0xd8},
	{0x1d, 0x40}, {0x1f, 0x40}, {0x21, 0x40}, {0x06, 0x00}, {0x07, 0x3f},
	{0x1d, 0x40}, {0x1f, 0x40}, {0x21, 0x40}, {0x2a, 0x27}, {0x2b, 0x27},
	{0x06, 0x20}, {0x10, 0xc1}, {0x11, 0x18}, {0x13, 0x00}, {0x0c, 0xcf},
	{0x07, 0xff}, {0x2c, 0x27}, {0x2d, 0x27}, {0x28, 0x27}, {0x29, 0x27},
	{0x06, 0x20}, {0x0a, 0x00}, {0x1b, 0x00}, {0x1c, 0x00}, {0x07, 0xff},
	{0x1d, 0x40}, {0x1f, 0x40}, {0x21, 0x40}, {0x07, 0xff}, {0x35, 0x00},
	{0x36, 0x80}, {0x37, 0xff}, {0x08, 0x01}, {0x06, 0x38}, {0x06, 0xb8},
	{0x30, 0x02}, {0x35, 0x00}, {0x36, 0x80}, {0x37, 0xff}, {0x0a, 0x0b},
};
static const uint8_t playback[][2] = {
	{0x07, 0xfc}, {0x1d, 0x40}, {0x1f, 0x40}, {0x21, 0x78}, {0x2a, 0x00},
	{0x2b, 0x00}, {0x06, 0xb8},
};
static const uint8_t stop[][2] = {
	{0x07, 0xff}, {0x21, 0x40}, {0x2a, 0x27}, {0x2b, 0x27},
};

static int i2c;

static void wr(uint8_t reg, uint8_t val)
{
	uint8_t b[2] = { reg, val };
	struct i2c_msg m = { .addr = 0x4a, .len = 2, .buf = b };
	struct i2c_rdwr_ioctl_data d = { &m, 1 };

	if (ioctl(i2c, I2C_RDWR, &d) < 0) {
		perror("codec");
		exit(1);
	}
}

#define APPLY(t) for (unsigned i = 0; i < sizeof(t) / 2; i++) { \
	wr(t[i][0], t[i][1]); \
	if (t[i][0] == 0x3b) usleep(10000); }

static double now(void)
{
	struct timespec t;

	clock_gettime(CLOCK_MONOTONIC, &t);
	return t.tv_sec + t.tv_nsec / 1e9;
}

static volatile uint32_t *map(int mem, uint32_t page)
{
	void *p = mmap(0, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, mem, page);

	if (p == MAP_FAILED) {
		perror("mmap");
		exit(1);
	}
	return p;
}

int main(int argc, char **argv)
{
	int mem = open("/dev/mem", O_RDWR | O_SYNC);
	double seconds = argc > 2 ? atof(argv[2]) : 1.5, end;
	unsigned hz = argc > 1 ? atoi(argv[1]) : 600, half, n = 0;
	volatile uint32_t *i2s, *gpio, *gate;

	i2c = open("/dev/i2c-0", O_RDWR);
	if (mem < 0 || i2c < 0 || hz < 50 || hz > 5000)
		return 2;
	if (seconds > 3)
		seconds = 3;
	half = RATE / 2 / hz;
	/* I2S0 clock gate is off after boot; touching the block then can hang. */
	gate = map(mem, 0xbf101000) + 0x94 / 4;
	*gate |= 0xf;
	usleep(10000);
	i2s = map(mem, 0x84500000) + 0x400 / 4;
	gpio = map(mem, 0xbfa00000) + SPEAKER_PIN;

	APPLY(startup);
	APPLY(playback);
	*gpio = 0x203;
	i2s[0x410 / 4] = 0x28000300;
	i2s[0x3c / 4] = 1;
	i2s[0x04 / 4] = 0x03100099;
	i2s[0x30 / 4] = 0x1000;
	i2s[0x08 / 4] = 0;
	i2s[0x34 / 4] = 0;
	i2s[0x40 / 4] = 0;
	i2s[0] = 0x181;
	i2s[0x08 / 4] = 6;

	for (end = now() + seconds; now() < end;) {
		if (((i2s[0x3c / 4] >> 7) & 31) < 12) {
			/* one 16-bit sample per write, left then right */
			int16_t s = (n / 2 / half) & 1 ? AMPLITUDE : -AMPLITUDE;

			i2s[0x10 / 4] = (uint16_t)s;
			n++;
		}
	}

	i2s[0x08 / 4] = 0;
	*gpio = 0x202;
	i2s[0] = 0x1a0;
	i2s[0x410 / 4] = 0x20000300;
	APPLY(stop);
	printf("%u samples (expected ~%u)\n", n, (unsigned)(seconds * RATE * 2));
	return n < seconds * RATE;
}
