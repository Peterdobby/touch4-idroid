// SPDX-License-Identifier: GPL-2.0
/* 32-bit register access: mem ADDR [VALUE]. Reads unless VALUE is given. */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <unistd.h>

int main(int argc, char **argv)
{
	unsigned long addr;
	int fd = open("/dev/mem", O_RDWR | O_SYNC);
	volatile uint32_t *p;

	if (argc < 2 || fd < 0)
		return 2;
	addr = strtoul(argv[1], 0, 0);
	if (addr & 3)
		return 2;
	p = mmap(0, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd, addr & ~0xfffUL);
	if (p == MAP_FAILED) {
		perror("mmap");
		return 1;
	}
	p += (addr & 0xfff) / 4;
	if (argc > 2)
		*p = strtoul(argv[2], 0, 0);
	printf("0x%08lx = 0x%08x\n", addr, *p);
	return 0;
}
