/* N81AP iBSS 4.1 (8B117) only. Original syringe's jump calls iBSS
 * jump_to(0, entry, 0); a direct branch bypasses its shutdown/cache/MMU work.
 * The function address is verified against the exact decrypted iBSS.
 * No storage command, installer, or custom cache geometry probe is used.
 */
.syntax unified
.cpu cortex-a8
.arm
.text
.global _start
_start:
    mov r0, #0
    ldr r1, =openiboot_image
    mov r2, #0
    ldr r3, =0x8401496d
    bx r3
.ltorg
.balign 4096
openiboot_image:
    .incbin "openiboot.bin"
