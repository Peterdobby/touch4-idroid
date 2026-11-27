/*
 * The N81AP's four buttons as an ordinary input device ("n81-buttons"), so that
 * programs do not read hardware: GPIO pins 0..3 (Home, Power, Volume up,
 * Volume down, active low) are sampled and reported through uinput.
 */
#include <fcntl.h>
#include <linux/input.h>
#include <linux/uinput.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

#define GPIO_BASE 0xbfa00000u

static const int codes[4] = { KEY_HOMEPAGE, KEY_POWER, KEY_VOLUMEUP, KEY_VOLUMEDOWN };

static void emit(int fd, int type, int code, int value)
{
	struct input_event ev = { .type = type, .code = code, .value = value };

	if (write(fd, &ev, sizeof(ev)) != sizeof(ev))
		perror("uinput");
}

int main(void)
{
	struct uinput_user_dev device = { .id = { .bustype = BUS_HOST } };
	volatile uint32_t *gpio;
	unsigned before = 0, last = 0;
	int mem, out;

	mem = open("/dev/mem", O_RDONLY | O_SYNC);
	if (mem < 0) {
		perror("/dev/mem");
		return 1;
	}
	gpio = mmap(NULL, 4096, PROT_READ, MAP_SHARED, mem, (off_t)GPIO_BASE);
	if (gpio == MAP_FAILED) {
		perror("mmap");
		return 1;
	}
	out = open("/dev/uinput", O_WRONLY);
	if (out < 0) {
		perror("/dev/uinput");
		return 1;
	}
	ioctl(out, UI_SET_EVBIT, EV_KEY);
	for (int i = 0; i < 4; i++)
		ioctl(out, UI_SET_KEYBIT, codes[i]);
	strcpy(device.name, "n81-buttons");
	if (write(out, &device, sizeof(device)) != sizeof(device) || ioctl(out, UI_DEV_CREATE)) {
		perror("uinput");
		return 1;
	}
	for (;;) {
		unsigned now = 0, stable;

		for (int pin = 0; pin < 4; pin++)
			if (!(gpio[pin] & 1))
				now |= 1u << pin;
		/* a change counts once two samples in a row agree */
		stable = (now & last) | (before & (now | last));
		last = now;
		for (int i = 0; i < 4; i++)
			if ((stable ^ before) & (1u << i)) {
				emit(out, EV_KEY, codes[i], !!(stable & (1u << i)));
				emit(out, EV_SYN, SYN_REPORT, 0);
			}
		before = stable;
		usleep(20000);
	}
}
