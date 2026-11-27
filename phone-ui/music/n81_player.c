#include "n81_player.h"

#include <dirent.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

#define TRACKS 200

struct file_iterator {
	char dir[200];
	char *names[TRACKS];
	size_t count, index;
};

static pid_t player;		/* process group of the running track */
static int playing_index = -1;

static int by_name(const void *a, const void *b)
{
	return strcmp(*(char *const *)a, *(char *const *)b);
}

esp_err_t bsp_extra_player_init(void)
{
	return ESP_OK;
}

esp_err_t bsp_extra_file_instance_init(const char *dir, file_iterator_instance_t **out)
{
	static struct file_iterator it;
	const char *override = getenv("MUSIC_DIR");
	struct dirent *entry;
	DIR *d;

	for (size_t i = 0; i < it.count; i++)
		free(it.names[i]);
	it.count = it.index = 0;
	snprintf(it.dir, sizeof(it.dir), "%s", override ? override : dir);
	d = opendir(it.dir);
	while (d && (entry = readdir(d)) && it.count < TRACKS) {
		const char *dot = strrchr(entry->d_name, '.');

		if (dot && !strcasecmp(dot, ".mp3"))
			it.names[it.count++] = strdup(entry->d_name);
	}
	if (d)
		closedir(d);
	qsort(it.names, it.count, sizeof(it.names[0]), by_name);
	*out = &it;
	return ESP_OK;
}

size_t file_iterator_get_count(file_iterator_instance_t *it)
{
	return it->count;
}

size_t file_iterator_get_index(file_iterator_instance_t *it)
{
	return it->index;
}

void file_iterator_set_index(file_iterator_instance_t *it, size_t index)
{
	if (index < it->count)
		it->index = index;
}

const char *file_iterator_get_name_from_index(file_iterator_instance_t *it, size_t index)
{
	return index < it->count ? it->names[index] : NULL;
}

uint32_t n81_track_seconds(file_iterator_instance_t *it, size_t index)
{
	/* kbit/s of MPEG-1 and MPEG-2 layer III, by header index */
	static const int v1[16] = { 0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320 };
	static const int v2[16] = { 0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160 };
	unsigned char head[10], frame[4096];
	char path[512];
	long start = 0, size;
	uint32_t seconds = 0;
	size_t n;
	FILE *f;

	if (index >= it->count)
		return 0;
	snprintf(path, sizeof(path), "%s/%s", it->dir, it->names[index]);
	f = fopen(path, "rb");
	if (!f)
		return 0;
	if (fread(head, 1, 10, f) == 10 && !memcmp(head, "ID3", 3))
		start = 10 + ((head[6] << 21) | (head[7] << 14) | (head[8] << 7) | head[9]);
	fseek(f, 0, SEEK_END);
	size = ftell(f);
	fseek(f, start, SEEK_SET);
	n = fread(frame, 1, sizeof(frame), f);
	for (size_t i = 0; i + 3 < n; i++) {
		int version, kbps;

		if (frame[i] != 0xff || (frame[i + 1] & 0xe6) != 0xe2)
			continue;
		version = (frame[i + 1] >> 3) & 3;
		kbps = (version == 3 ? v1 : v2)[frame[i + 2] >> 4];
		if (!kbps)
			continue;
		/* right for constant bit rate; an estimate otherwise */
		seconds = (uint32_t)((size - start) / (kbps * 125));
		/* a variable bit rate file says how many frames it has */
		for (size_t k = i + 4; k + 12 <= n && k < i + 48; k++) {
			static const int rates[4] = { 44100, 48000, 32000, 0 };
			int rate = rates[(frame[i + 2] >> 2) & 3] / (version == 3 ? 1 : version == 2 ? 2 : 4);
			uint32_t frames;

			if ((memcmp(frame + k, "Xing", 4) && memcmp(frame + k, "Info", 4)) ||
			    !(frame[k + 7] & 1) || !rate)
				continue;
			frames = (uint32_t)frame[k + 8] << 24 | frame[k + 9] << 16 |
				 frame[k + 10] << 8 | frame[k + 11];
			seconds = (uint32_t)((uint64_t)frames * (version == 3 ? 1152 : 576) / rate);
			break;
		}
		break;
	}
	fclose(f);
	return seconds;
}

static void stop(void)
{
	if (player > 0) {
		kill(-player, SIGCONT);
		kill(-player, SIGKILL);
		waitpid(player, NULL, 0);
		player = 0;
	}
	playing_index = -1;
}

bool bsp_extra_player_is_playing_by_index(file_iterator_instance_t *it, int index)
{
	(void)it;
	return player > 0 && playing_index == index;
}

esp_err_t bsp_extra_player_play_index(file_iterator_instance_t *it, int index)
{
	char path[512];

	stop();
	if (index < 0 || (size_t)index >= it->count)
		return ESP_FAIL;
	snprintf(path, sizeof(path), "%s/%s", it->dir, it->names[index]);
	player = fork();
	if (player == 0) {
		setpgid(0, 0);
#ifdef DEVICE
		execl("/bin/sh", "sh", "/bin/bt-audio", "play", path, (char *)NULL);
		_exit(127);
#else
		fprintf(stderr, "play %s\n", path);
		sleep(20);
		_exit(0);
#endif
	}
	if (player < 0)
		return ESP_FAIL;
	setpgid(player, player);
	playing_index = index;
	return ESP_OK;
}

esp_err_t audio_player_pause(void)
{
	if (player > 0)
		kill(-player, SIGSTOP);
	return ESP_OK;
}

esp_err_t audio_player_resume(void)
{
	if (player > 0)
		kill(-player, SIGCONT);
	return ESP_OK;
}

bool n81_player_finished(void)
{
	if (player <= 0 || waitpid(player, NULL, WNOHANG) != player)
		return false;
	player = 0;
	playing_index = -1;
	return true;
}
