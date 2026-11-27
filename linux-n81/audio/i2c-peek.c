// SPDX-License-Identifier: GPL-2.0
/* Read-only register dump: i2c-peek ADDR [FIRST [COUNT]] */
#include <fcntl.h>
#include <linux/i2c-dev.h>
#include <linux/i2c.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>

int main(int argc, char **argv)
{
	int addr = argc > 1 ? strtol(argv[1], 0, 0) : 0x4a;
	int first = argc > 2 ? strtol(argv[2], 0, 0) : 0;
	int count = argc > 3 ? strtol(argv[3], 0, 0) : 0x40;
	int fd = open("/dev/i2c-0", O_RDWR), r, bad = 0;

	if (fd < 0) {
		perror("i2c");
		return 1;
	}
	for (r = first; r < first + count; r++) {
		uint8_t reg = r, val = 0;
		struct i2c_msg m[2] = {
			{ .addr = addr, .len = 1, .buf = &reg },
			{ .addr = addr, .flags = I2C_M_RD, .len = 1, .buf = &val },
		};
		struct i2c_rdwr_ioctl_data d = { m, 2 };

		if ((r - first) % 16 == 0)
			printf("\n%02x:", r);
		if (ioctl(fd, I2C_RDWR, &d) < 0) {
			printf(" --");
			if (++bad > 3)
				break;
		} else {
			printf(" %02x", val);
		}
	}
	printf("\n");
	return bad ? 1 : 0;
}
