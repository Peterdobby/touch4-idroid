// SPDX-License-Identifier: GPL-2.0
/*
 * CS42L59 register tool. "codec init" applies the start-up sequence read from
 * AppleCS42L59Audio (iOS 10B500); "codec w REG VAL" and "codec u REG MASK VAL"
 * write; "codec dump" shows 0x00-0x3f.
 */
#include <fcntl.h>
#include <linux/i2c-dev.h>
#include <linux/i2c.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define CODEC 0x4a
static int fd;

static int rd(int reg)
{
	uint8_t r = reg, v = 0;
	struct i2c_msg m[2] = {
		{ .addr = CODEC, .len = 1, .buf = &r },
		{ .addr = CODEC, .flags = I2C_M_RD, .len = 1, .buf = &v },
	};
	struct i2c_rdwr_ioctl_data d = { m, 2 };

	if (ioctl(fd, I2C_RDWR, &d) < 0) {
		perror("i2c read");
		exit(1);
	}
	return v;
}

static void wr(int reg, int val)
{
	uint8_t b[2] = { reg, val };
	struct i2c_msg m = { .addr = CODEC, .len = 2, .buf = b };
	struct i2c_rdwr_ioctl_data d = { &m, 1 };

	if (ioctl(fd, I2C_RDWR, &d) < 0) {
		perror("i2c write");
		exit(1);
	}
}

static void up(int reg, int mask, int val)
{
	wr(reg, (rd(reg) & ~mask) | (val & mask));
}

static void init(void)
{
	wr(0x3b, 0xa5);
	usleep(10000);
	wr(0x3b, 0x00);
	up(0x07, 0x3c, 0x00);
	up(0x09, 0x20, 0x20);
	up(0x09, 0x0e, 0x00);
	wr(0x0a, 0x0b);
	usleep(10000);
	wr(0x0c, 0xc0);
	up(0x1a, 0x01, 0x01);
	up(0x10, 0x01, 0x01);
	up(0x0e, 0x10, 0x10);
	wr(0x1d, 0x40);
	wr(0x1f, 0x40);
	wr(0x21, 0x40);
	up(0x06, 0x03, 0x00);
}

static void dump(void)
{
	for (int r = 0; r < 0x40; r++)
		printf("%s%02x%s", r % 16 ? " " : "", rd(r), r % 16 == 15 ? "\n" : "");
}

int main(int argc, char **argv)
{
	const char *cmd = argc > 1 ? argv[1] : "dump";

	fd = open("/dev/i2c-0", O_RDWR);
	if (fd < 0) {
		perror("i2c");
		return 1;
	}
	if (!strcmp(cmd, "init"))
		init();
	else if (!strcmp(cmd, "w") && argc > 3)
		wr(strtol(argv[2], 0, 0), strtol(argv[3], 0, 0));
	else if (!strcmp(cmd, "u") && argc > 4)
		up(strtol(argv[2], 0, 0), strtol(argv[3], 0, 0), strtol(argv[4], 0, 0));
	dump();
	return 0;
}
