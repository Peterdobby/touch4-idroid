// ESP-Brookesia's phone on Linux: /dev/fb0, touch and buttons on the iPod.
// On the PC: phone --shot DIR saves screens.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#ifdef DEVICE
#include <fcntl.h>
#include <linux/input.h>
#include <linux/kd.h>
#include <signal.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#endif

#include "esp_brookesia.hpp"
#include "Calculator.hpp"
#include "MusicPlayer.hpp"
#include "Setting.hpp"

#define W 640
#define H 960

static lv_color_t memory[W * H];
static lv_color_t *screen = memory;   // the framebuffer on the iPod
static int touch_x, touch_y, touch_down;

static void flush(lv_disp_drv_t *driver, const lv_area_t *area, lv_color_t *pixels)
{
    for (int y = area->y1; y <= area->y2; y++) {
        int width = area->x2 - area->x1 + 1;
        memcpy(&screen[y * W + area->x1], pixels, width * sizeof(lv_color_t));
        pixels += width;
    }
    lv_disp_flush_ready(driver);
}

// the status bar shows what the platform reports, and nothing it cannot know
static void status_update(lv_timer_t *timer)
{
    ESP_Brookesia_StatusBar *bar = ((ESP_Brookesia_Phone *)timer->user_data)->getHome().getStatusBar();
    time_t seconds = time(NULL);
    struct tm *now = localtime(&seconds);
    int connected = 0;

    if (bar == NULL) {
        return;
    }
    // the iPod has no battery-backed clock: 1970 until set over the network
    if (now != NULL && now->tm_year >= 124) {
        bar->setClock(now->tm_hour, now->tm_min, now->tm_hour >= 12);
    }
#ifdef DEVICE
    FILE *link = popen("n81-wifi link 2>/dev/null", "r");
    if (link != NULL) {
        char line[128] = "";
        connected = fgets(line, sizeof(line), link) != NULL && !strncmp(line, "connected ", 10);
        pclose(link);
    }
#endif
    bar->setWifiIconState(connected ? ESP_Brookesia_StatusBar::WifiState::SIGNAL_3 :
                          ESP_Brookesia_StatusBar::WifiState::DISCONNECTED);
}

#ifdef DEVICE
static int touch_fd = -1, keys_fd = -1, console_fd = -1;

static void console_restore(int signal_number)
{
    ioctl(console_fd, KDSETMODE, KD_TEXT);
    _exit(128 + signal_number);
}

// an input device by name, grabbed so that the old menu does not act on it too
static int input_open(const char *wanted)
{
    for (int i = 0; i < 16; i++) {
        char path[32], name[96] = "";
        snprintf(path, sizeof(path), "/dev/input/event%d", i);
        int fd = open(path, O_RDONLY | O_NONBLOCK);
        if (fd < 0) {
            continue;
        }
        if (ioctl(fd, EVIOCGNAME(sizeof(name) - 1), name) > 0 && strstr(name, wanted)) {
            ioctl(fd, EVIOCGRAB, 1);
            return fd;
        }
        close(fd);
    }
    return -1;
}

static int device_start(void)
{
    int fb = open("/dev/fb0", O_RDWR);
    if (fb < 0) {
        perror("/dev/fb0");
        return -1;
    }
    void *map = mmap(NULL, W * H * 4, PROT_READ | PROT_WRITE, MAP_SHARED, fb, 0);
    if (map == MAP_FAILED) {
        perror("mmap");
        return -1;
    }
    screen = (lv_color_t *)map;
    // the text console would keep drawing its cursor and messages over us
    console_fd = open("/dev/tty0", O_RDWR | O_NOCTTY);
    if (console_fd >= 0 && !ioctl(console_fd, KDSETMODE, KD_GRAPHICS)) {
        signal(SIGINT, console_restore);
        signal(SIGTERM, console_restore);
        signal(SIGHUP, console_restore);
    }
    touch_fd = input_open("multitouch");
    keys_fd = input_open("n81-buttons");
    return touch_fd < 0 ? -1 : 0;
}
#endif

static void touch_read(lv_indev_drv_t *driver, lv_indev_data_t *data)
{
#ifdef DEVICE
    struct input_event ev;
    while (read(touch_fd, &ev, sizeof(ev)) == sizeof(ev)) {
        if (ev.type == EV_ABS && ev.code == ABS_X) {
            touch_x = ev.value;
        } else if (ev.type == EV_ABS && ev.code == ABS_Y) {
            touch_y = ev.value;
        } else if (ev.type == EV_KEY && ev.code == BTN_TOUCH) {
            touch_down = ev.value;
        } else if (ev.type == EV_SYN) {
            // one frame at a time, so that a short tap is not lost
            data->continue_reading = true;
            break;
        }
    }
#endif
    data->point.x = touch_x;
    data->point.y = touch_y;
    data->state = touch_down ? LV_INDEV_STATE_PRESSED : LV_INDEV_STATE_RELEASED;
}

static void run_for(int ms)
{
    for (int i = 0; i < ms / 10; i++) {
        lv_tick_inc(10);
        lv_timer_handler();
    }
}

static void save(const char *dir, int n)
{
    char path[256];
    snprintf(path, sizeof(path), "%s/%d.ppm", dir, n);
    FILE *f = fopen(path, "wb");
    if (!f) {
        return;
    }
    fprintf(f, "P6\n%d %d\n255\n", W, H);
    for (int i = 0; i < W * H; i++) {
        unsigned char rgb[3] = { screen[i].ch.red, screen[i].ch.green, screen[i].ch.blue };
        fwrite(rgb, 1, 3, f);
    }
    fclose(f);
}

int main(int argc, char **argv)
{
    static lv_color_t buffer[W * H];
    static lv_disp_draw_buf_t draw;
    static lv_disp_drv_t driver;

    lv_init();
    lv_disp_draw_buf_init(&draw, buffer, NULL, W * H);
    lv_disp_drv_init(&driver);
    driver.hor_res = W;
    driver.ver_res = H;
    driver.draw_buf = &draw;
    driver.flush_cb = flush;
    lv_disp_drv_register(&driver);

#ifdef DEVICE
    if (device_start()) {
        return 1;
    }
#endif
    static lv_indev_drv_t touch;
    lv_indev_drv_init(&touch);
    touch.type = LV_INDEV_TYPE_POINTER;
    touch.read_cb = touch_read;
    lv_indev_drv_register(&touch);

    ESP_Brookesia_Phone *phone = new ESP_Brookesia_Phone();
    ESP_Brookesia_PhoneStylesheet_t *style =
        new ESP_Brookesia_PhoneStylesheet_t ESP_BROOKESIA_PHONE_720_1280_DARK_STYLESHEET();
    // the closest portrait style, for this panel's size
    style->core.screen_size = ESP_BROOKESIA_STYLE_SIZE_RECT(W, H);
    // its recents cards are taller than this screen: scale them from 1280 to 960
    style->home.recents_screen.data.snapshot_table.snapshot.main_size = ESP_BROOKESIA_STYLE_SIZE_RECT(450, 660);
    style->home.recents_screen.data.snapshot_table.snapshot.title.main_size = ESP_BROOKESIA_STYLE_SIZE_RECT(450, 60);
    style->home.recents_screen.data.snapshot_table.snapshot.image.main_size = ESP_BROOKESIA_STYLE_SIZE_RECT(450, 600);
    style->home.app_launcher.data.table.size = ESP_BROOKESIA_STYLE_SIZE_RECT_W_PERCENT(100, 760);
    // 24-hour clock; no battery reading exists yet, so no battery indicator
    style->home.status_bar.data.flags.enable_battery_icon = 0;
    style->home.status_bar.data.flags.enable_battery_label = 0;
    if (!phone->addStylesheet(*style) || !phone->activateStylesheet(*style) || !phone->begin()) {
        fprintf(stderr, "phone failed to start\n");
        return 1;
    }
    phone->installApp(new MusicPlayer());
    phone->installApp(new Calculator());
    phone->installApp(new AppSettings());
    ESP_Brookesia_StatusBar *bar = phone->getHome().getStatusBar();
    if (bar != NULL) {
        bar->setClockFormat(ESP_Brookesia_StatusBar::ClockFormat::FORMAT_24H);
    }
    lv_timer_t *status = lv_timer_create(status_update, 5000, phone);
    status_update(status);

    // --shot DIR [X,Y ...]: save the home screen, then tap each point and save
    if (argc >= 3 && !strcmp(argv[1], "--shot")) {
        run_for(1000);
        save(argv[2], 0);
        for (int i = 3; i < argc; i++) {
            if (sscanf(argv[i], "%d,%d", &touch_x, &touch_y) != 2) {
                return 2;
            }
            touch_down = 1;
            run_for(100);
            touch_down = 0;
            // commands run beside the interface: give them real time too
            for (int n = 0; n < 300; n++) {
                run_for(10);
                usleep(10000);
            }
            save(argv[2], i - 2);
        }
        return 0;
    }
#ifdef DEVICE
    struct timespec before, now;
    clock_gettime(CLOCK_MONOTONIC, &before);
    for (;;) {
        struct input_event ev;
        while (keys_fd >= 0 && read(keys_fd, &ev, sizeof(ev)) == sizeof(ev)) {
            if (ev.type != EV_KEY || ev.value != 1) {
                continue;
            }
            if (ev.code == KEY_HOMEPAGE) {
                phone->sendNavigateEvent(ESP_BROOKESIA_CORE_NAVIGATE_TYPE_HOME);
            } else if (ev.code == KEY_VOLUMEUP && system("bt-audio volume up &")) {
                fprintf(stderr, "volume failed\n");
            } else if (ev.code == KEY_VOLUMEDOWN && system("bt-audio volume down &")) {
                fprintf(stderr, "volume failed\n");
            }
        }
        clock_gettime(CLOCK_MONOTONIC, &now);
        lv_tick_inc((now.tv_sec - before.tv_sec) * 1000 + (now.tv_nsec - before.tv_nsec) / 1000000);
        before = now;
        lv_timer_handler();
        usleep(10000);
    }
#endif
    return 0;
}
