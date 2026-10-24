/* Re-enter the unchanged public hardware/console initialization, then execute
 * the already hardware-tested TOUCH03 handoff and immutable Android payloads.
 * Filesystem loading belongs to the external, existing iBoot environment. */
#define CONSOLE ((void (*)(void))0x8209)
#define PRINT ((void (*)(const char *,...))0xf66d)
#define START ((void (*)(void))0x44000731)
void t4_android_entry(void)
{
    CONSOLE();
    PRINT("[T4_MENU_03] immutable TOUCH03 payloads loaded from local boot file\n");
    START();
    PRINT("[T4_MENU_03] Android handoff returned; retain console for diagnosis\n");
}
