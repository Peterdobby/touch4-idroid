/* The music app's hooks into the system: files in a folder, played by bt-audio. */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef int esp_err_t;
#define ESP_OK 0
#define ESP_FAIL -1

typedef struct file_iterator file_iterator_instance_t;

esp_err_t bsp_extra_player_init(void);
esp_err_t bsp_extra_file_instance_init(const char *dir, file_iterator_instance_t **out);
size_t file_iterator_get_count(file_iterator_instance_t *it);
size_t file_iterator_get_index(file_iterator_instance_t *it);
void file_iterator_set_index(file_iterator_instance_t *it, size_t index);
const char *file_iterator_get_name_from_index(file_iterator_instance_t *it, size_t index);

bool bsp_extra_player_is_playing_by_index(file_iterator_instance_t *it, int index);
esp_err_t bsp_extra_player_play_index(file_iterator_instance_t *it, int index);
esp_err_t audio_player_pause(void);
esp_err_t audio_player_resume(void);

/* length estimated from the file; 0 if unknown */
uint32_t n81_track_seconds(file_iterator_instance_t *it, size_t index);
/* true once, when the track played to its end */
bool n81_player_finished(void);

#ifdef __cplusplus
}
#endif
