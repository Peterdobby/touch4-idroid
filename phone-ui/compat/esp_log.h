/* The few ESP-IDF logging macros the phone UI and its apps use. */
#pragma once
#include <stdio.h>
#define ESP_LOG_(level, tag, format, ...) fprintf(stderr, level " %s: " format "\n", tag, ##__VA_ARGS__)
#define ESP_LOGE(tag, format, ...) ESP_LOG_("E", tag, format, ##__VA_ARGS__)
#define ESP_LOGW(tag, format, ...) ESP_LOG_("W", tag, format, ##__VA_ARGS__)
#define ESP_LOGI(tag, format, ...) ESP_LOG_("I", tag, format, ##__VA_ARGS__)
#define ESP_LOGD(tag, format, ...) do { (void)(tag); } while (0)
#define ESP_LOGV(tag, format, ...) do { (void)(tag); } while (0)
