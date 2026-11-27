// SPDX-License-Identifier: GPL-2.0
/*
 * n81-play FILE.wav        play a 16-bit PCM WAV through /dev/dsp
 * n81-play -t              play a short test scale
 * n81-play -v PERCENT      set the speaker volume (0-100)
 * 44100, 22050 and 11025 Hz, mono or stereo; the slower rates repeat samples.
 */
#include <fcntl.h>
#include <sound/asound.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/soundcard.h>
#include <unistd.h>

static int volume(int percent)
{
	int fd = open("/dev/snd/controlC0", O_RDWR);
	struct snd_ctl_elem_info info = { 0 };
	struct snd_ctl_elem_value value = { 0 };

	info.id.iface = SNDRV_CTL_ELEM_IFACE_MIXER;
	strcpy((char *)info.id.name, "Speaker Playback Volume");
	if (fd < 0 || ioctl(fd, SNDRV_CTL_IOCTL_ELEM_INFO, &info) < 0) {
		perror("mixer");
		return 1;
	}
	if (percent < 0 || percent > 100)
		percent = 50;
	value.id = info.id;
	value.value.integer.value[0] = info.value.integer.max * percent / 100;
	if (ioctl(fd, SNDRV_CTL_IOCTL_ELEM_WRITE, &value) < 0) {
		perror("mixer");
		return 1;
	}
	close(fd);
	return 0;
}

static int dsp_open(void)
{
	int fd = open("/dev/dsp", O_WRONLY), fmt = AFMT_S16_LE, ch = 2, rate = 44100;

	if (fd < 0 || ioctl(fd, SNDCTL_DSP_SETFMT, &fmt) < 0 || fmt != AFMT_S16_LE ||
	    ioctl(fd, SNDCTL_DSP_CHANNELS, &ch) < 0 || ch != 2 ||
	    ioctl(fd, SNDCTL_DSP_SPEED, &rate) < 0 || rate != 44100) {
		perror("/dev/dsp");
		exit(1);
	}
	return fd;
}

static void put(int fd, const void *p, size_t n)
{
	while (n) {
		ssize_t w = write(fd, p, n);

		if (w <= 0) {
			perror("write");
			exit(1);
		}
		p = (const char *)p + w;
		n -= w;
	}
}

static int scale(void)
{
	static const int notes[] = { 523, 587, 659, 698, 784, 880, 988, 1047 };
	static int16_t buf[1024 * 2];
	int fd = dsp_open();

	for (unsigned i = 0; i < 8; i++) {
		unsigned frames = 44100 / 4, period = 44100 / notes[i];

		for (unsigned done = 0; done < frames;) {
			unsigned n = frames - done < 1024 ? frames - done : 1024;

			for (unsigned k = 0; k < n; k++, done++) {
				/* triangle wave, faded at both ends to avoid clicks */
				int x = (int)(done % period) * 4 * 8000 / period;
				int v = x < 2 * 8000 ? x - 8000 : 3 * 8000 - x;
				unsigned edge = done < frames - done ? done : frames - done;

				if (edge < 441)
					v = v * (int)edge / 441;
				buf[2 * k] = buf[2 * k + 1] = v;
			}
			put(fd, buf, n * 4);
		}
	}
	close(fd);
	return 0;
}

static uint32_t le32(const uint8_t *p)
{
	return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24;
}

static int wav(const char *path)
{
	static int16_t in[1024], out[1024 * 8];
	FILE *f = fopen(path, "rb");
	uint8_t h[12], c[8], fmt[16];
	unsigned channels = 0, rate = 0, repeat, left = 0;
	int fd;

	if (!f || fread(h, 1, 12, f) != 12 || memcmp(h, "RIFF", 4) || memcmp(h + 8, "WAVE", 4)) {
		fprintf(stderr, "%s: not a WAV file\n", path);
		return 1;
	}
	while (fread(c, 1, 8, f) == 8) {
		uint32_t size = le32(c + 4);

		if (!memcmp(c, "data", 4)) {
			left = size;
			break;
		}
		if (!memcmp(c, "fmt ", 4) && size >= 16) {
			if (fread(fmt, 1, 16, f) != 16)
				break;
			if (fmt[0] != 1 || fmt[14] != 16)
				break;
			channels = fmt[2];
			rate = le32(fmt + 4);
			size -= 16;
		}
		if (fseek(f, size + (size & 1), SEEK_CUR))
			break;
	}
	repeat = rate == 44100 ? 1 : rate == 22050 ? 2 : rate == 11025 ? 4 : 0;
	if (!left || !repeat || (channels != 1 && channels != 2)) {
		fprintf(stderr, "%s: need 16-bit PCM, mono or stereo, 44100/22050/11025 Hz\n", path);
		return 1;
	}
	fd = dsp_open();
	while (left >= 2 * channels) {
		size_t want = left < sizeof(in) ? left : sizeof(in);
		size_t frames = fread(in, 1, want, f) / (2 * channels), n = 0;

		if (!frames)
			break;
		for (size_t i = 0; i < frames; i++)
			for (unsigned r = 0; r < repeat; r++) {
				out[n++] = in[i * channels];
				out[n++] = in[i * channels + channels - 1];
			}
		put(fd, out, n * 2);
		left -= frames * 2 * channels;
	}
	close(fd);
	return 0;
}

int main(int argc, char **argv)
{
	if (argc == 3 && !strcmp(argv[1], "-v"))
		return volume(atoi(argv[2]));
	if (argc == 2 && !strcmp(argv[1], "-t"))
		return scale();
	if (argc == 2 && argv[1][0] != '-')
		return wav(argv[1]);
	fprintf(stderr, "usage: n81-play FILE.wav | -t | -v 0-100\n");
	return 2;
}
