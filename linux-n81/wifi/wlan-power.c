// SPDX-License-Identifier: GPL-2.0
/* Switch the BCM4329 chip power: PMU GPIO register 0x58, bit 1, only. */
#include <fcntl.h>
#include <linux/i2c-dev.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

static int reg_read(int fd, uint8_t reg)
{
	uint8_t v = reg;

	return write(fd, &v, 1) == 1 && read(fd, &v, 1) == 1 ? v : -1;
}

int main(int argc, char **argv)
{
	int on = argc < 2 || strcmp(argv[1], "off");
	int fd = open("/dev/i2c-0", O_RDWR), before, after;
	uint8_t out[2] = { 0x58, 0 };

	if (fd < 0 || ioctl(fd, I2C_SLAVE_FORCE, 0x74) < 0) {
		perror("i2c");
		return 1;
	}
	before = reg_read(fd, 0x58);
	if (before < 0) {
		perror("pmu read");
		return 1;
	}
	out[1] = on ? before | 2 : before & ~2;
	if (write(fd, out, 2) != 2) {
		perror("pmu write");
		return 1;
	}
	after = reg_read(fd, 0x58);
	printf("pmu 0x58: 0x%02x -> 0x%02x\n", before, after);
	return after == out[1] ? 0 : 1;
}
