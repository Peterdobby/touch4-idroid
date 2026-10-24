/* Read-only identity probe. No user-client, storage or NVRAM writes. */
typedef unsigned U;
typedef unsigned long S;
typedef long I;
typedef const void *CF;
extern int printf(const char *, ...);
extern int sysctlbyname(const char *, void *, S *, void *, S);
extern U IORegistryEntryFromPath(U, const char *);
extern CF IORegistryEntryCreateCFProperty(U, CF, CF, U);
extern int IOObjectRelease(U);
extern CF CFStringCreateWithCString(CF, const char *, U);
extern S CFGetTypeID(CF);
extern S CFDataGetTypeID(void);
extern S CFNumberGetTypeID(void);
extern I CFDataGetLength(CF);
extern const unsigned char *CFDataGetBytePtr(CF);
extern int CFNumberGetValue(CF, int, void *);
extern void CFRelease(CF);
int main(void) {
    char machine[32] = {0}; S length = sizeof(machine);
    if (sysctlbyname("hw.machine", machine, &length, 0, 0)) return 2;
    const char *paths[] = {"IODeviceTree:/chosen", "IODeviceTree:/", 0};
    for (unsigned i = 0; paths[i]; i++) {
        U entry = IORegistryEntryFromPath(0, paths[i]);
        if (!entry) continue;
        CF key = CFStringCreateWithCString(0, "unique-chip-id", 0x08000100);
        CF value = IORegistryEntryCreateCFProperty(entry, key, 0, 0);
        CFRelease(key); IOObjectRelease(entry);
        if (!value) continue;
        unsigned long long little = 0, big = 0;
        if (CFGetTypeID(value) == CFDataGetTypeID()) {
            I n = CFDataGetLength(value);
            if (n > 0 && n <= 8) {
                const unsigned char *p = CFDataGetBytePtr(value);
                for (I j = 0; j < n; j++) { little |= (unsigned long long)p[j] << (8*j); big = (big << 8) | p[j]; }
            }
        } else if (CFGetTypeID(value) == CFNumberGetTypeID()) {
            if (CFNumberGetValue(value, 4, &little)) big = little;
        }
        CFRelease(value);
        if (little) {
            printf("{\"machine\":\"%s\",\"ecid_candidates\":[\"0x%llx\",\"0x%llx\"]}\n", machine, little, big);
            return 0;
        }
    }
    printf("{\"machine\":\"%s\",\"ecid_candidates\":[]}\n", machine);
    return 3;
}
