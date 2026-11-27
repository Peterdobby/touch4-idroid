/* PID 1 with a small on-screen menu for the N81AP RAM boot.
 * Freestanding: modern static glibc refuses to run on Linux 3.0.
 * Draws on /dev/fb0, reads the buttons from the GPIO registers (read only).
 * "--preview FB KEYS" renders into a plain file for testing on the host.
 */
#include "font.h" /* static const unsigned char font[256*16] */

typedef unsigned int u32;

#define W 640
#define H 960
#define CELL_W 16
#define CELL_H 32
#define COLS (W / CELL_W)
#define LINES (H / CELL_H)

static long sc(long n, long a, long b, long c, long d, long e, long f)
{
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    register long r3 __asm__("r3") = d;
    register long r4 __asm__("r4") = e;
    register long r5 __asm__("r5") = f;
    register long r7 __asm__("r7") = n;
    __asm__ volatile("svc 0" : "+r"(r0)
        : "r"(r1), "r"(r2), "r"(r3), "r"(r4), "r"(r5), "r"(r7) : "memory", "cc");
    return r0;
}
#define sys_exit(c)        sc(1, c, 0, 0, 0, 0, 0)
#define sys_fork()         sc(2, 0, 0, 0, 0, 0, 0)
#define sys_read(f, b, n)  sc(3, f, (long)(b), n, 0, 0, 0)
#define sys_write(f, b, n) sc(4, f, (long)(b), n, 0, 0, 0)
#define sys_open(p, fl)    sc(5, (long)(p), fl, 0, 0, 0, 0)
#define sys_close(f)       sc(6, f, 0, 0, 0, 0, 0)
#define sys_execve(p, a, e) sc(11, (long)(p), (long)(a), (long)(e), 0, 0, 0)
#define sys_mount(s, t, k) sc(21, (long)(s), (long)(t), (long)(k), 0, 0, 0)
#define sys_sync()         sc(36, 0, 0, 0, 0, 0, 0)
#define sys_mknod(p, m, d) sc(14, (long)(p), m, d, 0, 0, 0)
#define sys_setsid()       sc(66, 0, 0, 0, 0, 0, 0)
#define sys_pipe(p)        sc(42, (long)(p), 0, 0, 0, 0, 0)
#define sys_ioctl(f, r, a) sc(54, f, r, (long)(a), 0, 0, 0)
#define sys_dup2(a, b)     sc(63, a, b, 0, 0, 0, 0)
#define sys_reboot(cmd)    sc(88, 0xfee1dead, 672274793, cmd, 0, 0, 0)
#define sys_wait(p, s)     sc(114, p, (long)(s), 0, 0, 0, 0)
#define sys_nanosleep(t)   sc(162, (long)(t), 0, 0, 0, 0, 0)
#define sys_mmap2(len, prot, fl, fd, pg) sc(192, 0, len, prot, fl, fd, pg)

void *memset(void *d, int c, unsigned n)
{
    unsigned char *p = d;
    while (n--) *p++ = c;
    return d;
}
void *memcpy(void *d, const void *s, unsigned n)
{
    unsigned char *p = d;
    const unsigned char *q = s;
    while (n--) *p++ = *q++;
    return d;
}
int raise(int sig) { sys_exit(128 + sig); return 0; } /* libgcc div by zero */

static volatile u32 *screen;
static volatile u32 *gpio;
static const char *preview_keys;

static void msleep(int ms)
{
    long t[2];
    t[0] = ms / 1000;
    t[1] = (ms % 1000) * 1000000L;
    if (!preview_keys) sys_nanosleep(t);
}

/* ---- drawing ---- */
static void text(int line, int col, const char *s, u32 fg, u32 bg)
{
    int x, y;
    if (line < 0 || line >= LINES) return;
    for (; *s && col < COLS; s++, col++) {
        const unsigned char *g = font + (unsigned char)*s * 16;
        for (y = 0; y < CELL_H; y++)
            for (x = 0; x < CELL_W; x++)
                screen[(line * CELL_H + y) * W + col * CELL_W + x] =
                    (g[y / 2] & (0x80 >> (x / 2))) ? fg : bg;
    }
}
static void fill(int line, int count, u32 color)
{
    int i, end = (line + count) * CELL_H * W;
    for (i = line * CELL_H * W; i < end; i++) screen[i] = color;
}
static void row(int line, const char *s, u32 fg, u32 bg)
{
    fill(line, 1, bg);
    text(line, 1, s, fg, bg);
}

/* ---- tiny string helpers ---- */
static char *put(char *d, const char *s)
{
    while (*s) *d++ = *s++;
    *d = 0;
    return d;
}
static char *putnum(char *d, unsigned v, int width)
{
    char t[12];
    int n = 0;
    do { t[n++] = '0' + v % 10; v /= 10; } while (v);
    while (n < width) t[n++] = '0';
    while (n) *d++ = t[--n];
    *d = 0;
    return d;
}
static int slurp(const char *path, char *buf, int size)
{
    int fd = sys_open(path, 0), n = 0, got;
    if (fd < 0) { buf[0] = 0; return 0; }
    while (n < size - 1 && (got = sys_read(fd, buf + n, size - 1 - n)) > 0) n += got;
    sys_close(fd);
    buf[n] = 0;
    return n;
}
static unsigned number_after(const char *s, const char *key)
{
    unsigned v = 0;
    for (; *s; s++) {
        const char *a = s, *b = key;
        while (*b && *a == *b) a++, b++;
        if (*b) continue;
        while (*a == ' ') a++;
        while (*a >= '0' && *a <= '9') v = v * 10 + *a++ - '0';
        break;
    }
    return v;
}

/* ---- buttons: pins 0..3 are Home, Power, Vol+, Vol-; active low ---- */
enum { K_HOME = 1, K_POWER = 2, K_UP = 4, K_DOWN = 8, K_TAP = 16 };

/* ---- touch: any evdev device named "...multitouch...", opened when it appears */
struct input_event { u32 sec, usec; unsigned short type, code; int value; };
static long touch_fd = -1;
static int touch_x, touch_y, touch_down;

static int contains(const char *s, const char *part)
{
    for (; *s; s++) {
        const char *a = s, *b = part;
        while (*b && *a == *b) a++, b++;
        if (!*b) return 1;
    }
    return 0;
}
static void touch_open(void)
{
    char sys[] = "/sys/class/input/event0/device/name", dev[] = "/dev/input/event0";
    char name[80];
    int i, fd;
    for (i = 0; i < 6; i++) {
        sys[22] = dev[16] = '0' + i;
        fd = sc(5, (long)sys, 0, 0, 0, 0, 0);
        if (fd < 0) continue;
        name[sc(3, fd, (long)name, sizeof(name) - 1, 0, 0, 0) & 63] = 0;
        sc(6, fd, 0, 0, 0, 0, 0);
        if (contains(name, "multitouch")) {
            touch_fd = sc(5, (long)dev, 04000 /* O_NONBLOCK */, 0, 0, 0, 0);
            return;
        }
    }
}
/* Drains pending events; returns 1 when a finger has just been lifted. */
static int touch_poll(void)
{
    struct input_event ev[16];
    long n;
    int i, tapped = 0;
    if (touch_fd < 0) return 0;
    while ((n = sc(3, touch_fd, (long)ev, sizeof(ev), 0, 0, 0)) > 0)
        for (i = 0; i < (int)(n / sizeof(ev[0])); i++) {
            if (ev[i].type == 3 && ev[i].code == 0x35) touch_x = ev[i].value;
            if (ev[i].type == 3 && ev[i].code == 0x36) touch_y = ev[i].value;
            if (ev[i].type == 1 && ev[i].code == 0x14a) {
                if (touch_down && !ev[i].value) tapped = 1;
                touch_down = ev[i].value;
            }
        }
    return tapped;
}

static unsigned raw_keys(void)
{
    unsigned pin, k = 0;
    if (!gpio) return 0;
    for (pin = 0; pin < 4; pin++)
        if (!(gpio[pin] & 1)) k |= 1u << pin;
    return k;
}
/* Returns newly pressed keys, waiting at most about one second. */
static unsigned wait_keys(void)
{
    static unsigned stable, last;
    static int first = 1;
    int i;
    if (preview_keys) {
        char c = *preview_keys;
        if (!c) sys_exit(0);
        preview_keys++;
        return c == 'u' ? K_UP : c == 'd' ? K_DOWN : c == 'h' ? K_HOME : 0;
    }
    if (first) { stable = last = raw_keys(); first = 0; } /* ignore held keys */
    if (touch_fd < 0) touch_open();
    for (i = 0; i < 50; i++) {
        unsigned now = raw_keys(), edge = 0;
        if (touch_poll()) return K_TAP;
        if (now == last) { edge = now & ~stable; stable = now; }
        last = now;
        if (edge) return edge;
        msleep(20);
    }
    return 0;
}

/* ---- screens ---- */
#define BG 0x000000
#define FG 0xffffff
#define DIM 0x808080
#define ACCENT 0x00c000

static void header(const char *title)
{
    fill(0, LINES, BG);
    row(0, "iPod touch 4G - Linux", BG, ACCENT);
    row(2, title, ACCENT, BG);
}
static void status(int line)
{
    char buf[2048], out[64], *p;
    unsigned up, free_kb, total_kb;
    slurp("/proc/uptime", buf, sizeof(buf));
    up = number_after(buf, "");
    slurp("/proc/meminfo", buf, sizeof(buf));
    total_kb = number_after(buf, "MemTotal:");
    free_kb = number_after(buf, "MemFree:");
    p = put(out, "up ");
    p = putnum(p, up / 3600, 2); p = put(p, ":");
    p = putnum(p, up / 60 % 60, 2); p = put(p, ":");
    putnum(p, up % 60, 2);
    row(line, out, FG, BG);
    p = put(out, "free RAM ");
    p = putnum(p, free_kb / 1024, 1); p = put(p, " of ");
    p = putnum(p, total_kb / 1024, 1); put(p, " MB");
    row(line + 1, out, FG, BG);
}

/* Print command output, wrapped at the screen width; keeps the first page. */
static void show_output(const char *title, const char *cmd)
{
    static char out[4096];
    char line[COLS];
    int fds[2], n = 0, got, i, len = 0, y = 4, st;
    long pid;
    header(title);
    if (sys_pipe(fds) < 0) return;
    pid = sys_fork();
    if (pid == 0) {
        const char *argv[] = { "sh", "-c", cmd, 0 };
        const char *envp[] = { "PATH=/bin", 0 };
        sys_dup2(fds[1], 1);
        sys_dup2(fds[1], 2);
        sys_close(fds[0]);
        sys_close(fds[1]);
        sys_execve("/bin/busybox", argv, envp);
        sys_write(1, "busybox did not start\n", 22);
        sys_exit(127);
    }
    sys_close(fds[1]);
    while (n < (int)sizeof(out) && (got = sys_read(fds[0], out + n, sizeof(out) - n)) > 0) n += got;
    sys_close(fds[0]);
    if (pid > 0) sys_wait(pid, &st);
    for (i = 0; i <= n && y < LINES - 2; i++) {
        char c = i < n ? out[i] : '\n';
        if (c != '\n') line[len++] = c == '\t' ? ' ' : c;
        if (c == '\n' || len == COLS - 1) {
            line[len] = 0;
            if (i < n || len) text(y++, 0, line, FG, BG);
            len = 0;
        }
    }
    row(LINES - 1, "HOME: voltar", DIM, BG);
    while (!(wait_keys() & (K_HOME | K_POWER | K_TAP))) {}
}

/* A root shell on the USB serial gadget, restarted whenever it exits. */
static void run_wait(const char *const *argv, const char *tty)
{
    const char *envp[] = { "PATH=/bin", "HOME=/", "TERM=vt100", "PS1=ipod# ", 0 };
    int st;
    long pid = sys_fork();
    if (pid == 0) {
        if (tty) {
            int fd;
            sys_setsid();
            fd = sys_open(tty, 2);
            if (fd < 0) sys_exit(1);
            sys_ioctl(fd, 0x540e /* TIOCSCTTY */, 0);
            sys_dup2(fd, 0);
            sys_dup2(fd, 1);
            sys_dup2(fd, 2);
        }
        sys_execve("/bin/busybox", argv, envp);
        sys_exit(127);
    }
    if (pid > 0) sys_wait(pid, &st);
}

static void serial_shell(void)
{
    static const char *const shell[] = { "sh", "-i", 0 };
    char dev[32], *p;
    unsigned major = 0, minor = 0;
    if (sys_fork() != 0) return;
    while (!slurp("/sys/class/tty/ttyGS0/dev", dev, sizeof(dev))) msleep(1000);
    for (p = dev; *p >= '0' && *p <= '9'; p++) major = major * 10 + *p - '0';
    if (*p == ':') p++;
    for (; *p >= '0' && *p <= '9'; p++) minor = minor * 10 + *p - '0';
    sys_mknod("/dev/ttyGS0", 020600, major << 8 | minor);
    for (;;) {
        run_wait(shell, "/dev/ttyGS0");
        msleep(500);
    }
}

/* Starts the N81 touch driver when the image carries it. */
static void touch_service(void)
{
    static const char *const argv[] = { "driver", "serve", "/touch/fw.bin", "/touch/cal.bin", 0 };
    static const char *const envp[] = { 0 };
    long fd, out;
    fd = sys_open("/touch/driver", 0);
    if (fd < 0) return;
    sys_close(fd);
    if (sys_fork() != 0) return;
    sys_setsid();
    out = sc(5, (long)"/tmp/touch.log", 0101 /* O_WRONLY|O_CREAT */, 0644, 0, 0, 0);
    if (out >= 0) { sys_dup2(out, 1); sys_dup2(out, 2); }
    sys_execve("/touch/driver", argv, envp);
    sys_exit(127);
}

/* Brings up Wi-Fi in the background when the image carries it. */
static void wifi_service(void)
{
    static const char *const argv[] = { "sh", "/bin/wifi-up", 0 };
    long fd = sys_open("/bin/wifi-up", 0);
    if (fd < 0) return;
    sys_close(fd);
    if (sys_fork() != 0) return;
    sys_setsid();
    run_wait(argv, 0);
    sys_exit(0);
}

static void bluetooth_service(void)
{
    static const char *const argv[] = { "sh", "/bin/bt-boot", 0 };
    long fd = sys_open("/bin/bt-boot", 0);
    if (fd < 0) return;
    sys_close(fd);
    if (sys_fork() != 0) return;
    sys_setsid();
    run_wait(argv, 0);
    sys_exit(0);
}

static void sound_service(void)
{
    static const char *const argv[] = { "sh", "/bin/sound-up", 0 };
    long fd = sys_open("/bin/sound-up", 0);
    if (fd < 0) return;
    sys_close(fd);
    if (sys_fork() != 0) return;
    sys_setsid();
    run_wait(argv, 0);
    sys_exit(0);
}

/* The buttons as an input device, for programs that are not this menu. */
static void buttons_service(void)
{
    static const char *const argv[] = { "sh", "-c", "exec n81-buttons", 0 };
    long fd = sys_open("/bin/n81-buttons", 0);
    if (fd < 0) return;
    sys_close(fd);
    if (sys_fork() != 0) return;
    sys_setsid();
    run_wait(argv, 0);
    sys_exit(0);
}

/* Keep routine kernel messages (Wi-Fi events) from being drawn over the menu;
 * only emergencies still reach the screen. dmesg keeps everything. */
static void quiet_console(void)
{
    long fd = sys_open("/proc/sys/kernel/printk", 1);
    if (fd < 0) return;
    sys_write(fd, "3\n", 2);
    sys_close(fd);
}

static void button_test(void)
{
    static const char *names[] = { "HOME", "TOP", "VOLUME +", "VOLUME -" };
    unsigned i, k;
    int held = 0;
    header("Button test");
    row(LINES - 1, "hold HOME 2s to go back", DIM, BG);
    while (held < 40) {
        if (preview_keys) { wait_keys(); return; }
        k = raw_keys();
        for (i = 0; i < 4; i++)
            row(5 + i * 2, names[i], (k >> i & 1) ? BG : FG, (k >> i & 1) ? ACCENT : BG);
        held = (k & K_HOME) ? held + 1 : 0;
        msleep(50);
    }
}

/* Paints where the finger is, to check position and orientation. */
static void touch_test(void)
{
    int x, y;
    header("Touch test");
    row(4, "drag a finger across the screen", FG, BG);
    row(LINES - 1, "HOME: voltar", DIM, BG);
    if (touch_fd < 0) touch_open();
    if (touch_fd < 0) row(6, "no touch driver", FG, BG);
    /* the HOME press that opened this screen is still down */
    while (!preview_keys && (raw_keys() & K_HOME)) msleep(20);
    while (!(raw_keys() & K_HOME)) {
        touch_poll();
        if (preview_keys) return;
        if (touch_down)
            for (y = touch_y - 6; y < touch_y + 6; y++)
                for (x = touch_x - 6; x < touch_x + 6; x++)
                    if (x >= 0 && x < W && y >= 0 && y < H) screen[y * W + x] = ACCENT;
        msleep(5);
    }
    msleep(300);
}

static void color_test(void)
{
    static const u32 colors[] = { 0xff0000, 0x00ff00, 0x0000ff, 0xffffff };
    int i;
    fill(0, LINES, BG);
    for (i = 0; i < 4; i++) fill(i * 7 + 1, 7, colors[i]);
    row(LINES - 1, "HOME: voltar", FG, BG);
    while (!(wait_keys() & (K_HOME | K_POWER | K_TAP))) {}
}

static const struct { const char *label, *cmd; } items[] = {
    { "Sound test", "sh /bin/sound-test" },
    { "Wi-Fi", "n81-wifi link; ifconfig wlan0 | grep 'inet '; tail -n 8 /tmp/wifi.log" },
    { "Bluetooth", "sh /bin/bt-scan" },
    { "System", "uname -s -r -m; grep -E 'Processor|Hardware|BogoMIPS' /proc/cpuinfo; free" },
    { "Processes", "ps" },
    { "Files", "ls /" },
    { "Kernel messages", "dmesg | tail -n 12" },
    { "Button test", 0 },
    { "Color test", 0 },
    { "Touch test", 0 },
    { "Restart (back to iOS)", 0 },
};
#define ITEMS ((int)(sizeof(items) / sizeof(items[0])))

static void menu(void)
{
    static const char hex[] = "0123456789abcdef";
    int selected = 0, i, redraw = 1;
    char gpio_line[] = "buttons: 0";
    /* An image with the phone interface (phone-ui/) opens it
     * right away and waits: the menu comes back only if it ends. */
    static const char *const ui[] = { "sh", "/bin/start-ui", 0 };
    long ui_file = preview_keys ? -1 : sys_open("/bin/start-ui", 0);
    if (ui_file >= 0) {
        sys_close(ui_file);
        header("Opening the interface...");
        run_wait(ui, 0);
    }
    for (;;) {
        unsigned k;
        if (redraw) {
            header("Menu");
            for (i = 0; i < ITEMS; i++)
                row(7 + i * 2, items[i].label,
                    i == selected ? BG : FG, i == selected ? FG : BG);
            row(LINES - 2, "VOL +/-: move   HOME: open", DIM, BG);
            redraw = 0;
        }
        status(4);
        gpio_line[9] = hex[raw_keys()];
        row(LINES - 1, gpio_line, DIM, BG);
        k = wait_keys();
        if (!k) continue;
        redraw = 1;
        if (k & K_TAP) {
            /* items occupy two text rows each, starting at row 7 */
            int hit = (touch_y / CELL_H - 7) / 2;
            if (touch_y < 7 * CELL_H || hit >= ITEMS) continue;
            selected = hit;
            k = K_HOME;
        }
        if (k & K_UP) selected = (selected + ITEMS - 1) % ITEMS;
        else if (k & (K_DOWN | K_POWER)) selected = (selected + 1) % ITEMS;
        else if (k & K_HOME) {
            if (items[selected].cmd) show_output(items[selected].label, items[selected].cmd);
            else if (selected == ITEMS - 4) button_test();
            else if (selected == ITEMS - 3) color_test();
            else if (selected == ITEMS - 2) touch_test();
            else if (!preview_keys) {
                header("Restarting...");
                sys_sync();
                sys_reboot(0x01234567);
            }
        }
    }
}

static void say(const char *s)
{
    int fd = sys_open("/dev/kmsg", 1), n = 0;
    if (fd < 0) return;
    while (s[n]) n++;
    sys_write(fd, s, n);
    sys_close(fd);
}

__attribute__((used)) static void start(long *sp)
{
    long argc = sp[0];
    char **argv = (char **)(sp + 1);
    const char *fb_path = "/dev/fb0";
    struct { char id[16]; unsigned long smem_start; char rest[64]; } fix;
    unsigned long offset = 0;
    long fd, map;

    if (argc == 4 && argv[1][0] == '-' && argv[1][1] == '-') {
        fb_path = argv[2];
        preview_keys = argv[3];
    } else {
        sys_mount("devtmpfs", "/dev", "devtmpfs"); /* absent on the 3.0 build */
        sys_mount("proc", "/proc", "proc");
        sys_mount("sysfs", "/sys", "sysfs");
        say("<5>N81: Linux userspace is running\n");
        serial_shell();
        touch_service();
        wifi_service();
        sound_service();
        bluetooth_service();
        buttons_service();
        quiet_console();
    }
    fd = sys_open(fb_path, 2);
    if (fd >= 0) {
        memset(&fix, 0, sizeof(fix));
        if (sys_ioctl(fd, 0x4602 /* FBIOGET_FSCREENINFO */, &fix) == 0)
            offset = fix.smem_start & 0xfff;
        map = sys_mmap2(offset + W * H * 4, 3, 1, fd, 0);
        if ((unsigned long)map < 0xfffff000u) screen = (volatile u32 *)(map + offset);
    }
    if (!screen) {
        for (;;) {
            say("<3>N81: cannot map /dev/fb0\n");
            if (preview_keys) sys_exit(1);
            msleep(5000);
        }
    }
    if (!preview_keys) {
        fd = sys_open("/dev/mem", 04010000 /* O_RDONLY|O_SYNC */);
        if (fd >= 0) {
            map = sys_mmap2(4096, 1, 1, fd, 0xbfa00 /* GPIO 0xbfa00000 */);
            if ((unsigned long)map < 0xfffff000u) gpio = (volatile u32 *)map;
        }
        if (!gpio) say("<3>N81: cannot map GPIO; buttons disabled\n");
    }
    menu();
}

__attribute__((naked)) void _start(void)
{
    __asm__ volatile("mov r0, sp\n bic sp, sp, #7\n bl start\n");
}
