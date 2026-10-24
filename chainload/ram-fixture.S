/* Test fixture for the EXISTING controlled N81 8B117 iBSS RAM download/go.
 * This is external RAM placement, not part of the 12-byte chainloader.
 * No exploit, bootloader patch, storage, USB implementation, or iOS6 code.
 * Preserve the live iBSS stack, mode, MMU, caches and IRQ state until the
 * frozen OpeniBoot wrapper calls its existing native jump_to exactly once.
 */
.syntax unified
.cpu cortex-a8
.arm
.section .text.entry,"ax",%progbits
.global _start, relocated_begin, relocated_end
.global native_image, native_image_end, loader_image, loader_image_end
.global fixture_wrong_context, fixture_enter_loader
_start:
    mrs r0, cpsr
    and r0, r0, #0x1f
    cmp r0, #0x13
    bne fixture_wrong_context
    /* Exact existing 8B117 jump_to prefix, generated from pinned local raw. */
    ldr r0, =0x8401496c
    ldr r1, [r0]
    ldr r2, =IBSS_JUMP_WORD0
    cmp r1, r2
    bne fixture_wrong_context
    ldr r1, [r0, #4]
    ldr r2, =IBSS_JUMP_WORD1
    cmp r1, r2
    bne fixture_wrong_context
    ldr r1, [r0, #8]
    ldr r2, =IBSS_JUMP_WORD2
    cmp r1, r2
    bne fixture_wrong_context
    ldr r1, [r0, #12]
    ldr r2, =IBSS_JUMP_WORD3
    cmp r1, r2
    bne fixture_wrong_context

    adr r0, relocated_begin
    ldr r1, =0x44001000
    ldr r2, relocated_size
1:
    ldr r3, [r0], #4
    str r3, [r1], #4
    subs r2, r2, #4
    bne 1b
    ldr r0, =0x44001000
    mov r1, r0
    ldr r2, relocated_size
    add r1, r1, r2
    bl sync_code
    ldr r12, =0x44001000
    bx r12
fixture_wrong_context:
    movw r0, #0xe001
    bx lr                         /* Return to existing caller; do not boot. */

/* Cortex-A8 MVA cache maintenance; no cache/MMU enable-bit changes.
 * 32-byte steps cover every 64-byte A4 line, including range tails.
 * Cache geometry evidence: arch-arm/entry.sx and pinned iBSS 84015d80.
 */
sync_code:
    bic r0, r0, #31
    dsb sy
2:
    mcr p15, 0, r0, c7, c10, 1   /* Clean D line by MVA to PoC. */
    add r0, r0, #32
    cmp r0, r1
    blo 2b
    dsb sy
    mov r0, #0
    mcr p15, 0, r0, c7, c5, 0    /* Invalidate I-cache. */
    mcr p15, 0, r0, c7, c5, 6    /* Invalidate branch predictions. */
    dsb sy
    isb sy
    bx lr
.ltorg
relocated_size:
    .word relocated_end-relocated_begin
.balign 4
relocated_begin:
    /* Execute outside the download buffer before replacing its beginning. */
    ldr r0, =native_image
    ldr r1, =0x41000000
    ldr r2, =native_image_end
3:
    ldr r3, [r0], #4
    str r3, [r1], #4
    cmp r0, r2
    blo 3b
    ldr r0, =loader_image
    ldr r1, =0x44000000
    ldr r2, =loader_image_end
4:
    ldr r3, [r0], #4
    str r3, [r1], #4
    cmp r0, r2
    blo 4b
    ldr r0, =0x41000000
    ldr r1, =(0x41000000+NATIVE_IMAGE_SIZE)
    bl relocated_sync
    ldr r0, =0x44000000
    ldr r1, =(0x44000000+LOADER_IMAGE_SIZE)
    bl relocated_sync
fixture_enter_loader:
    ldr r12, =0x44000000
    bx r12
relocated_sync:
    bic r0, r0, #31
    dsb sy
5:
    mcr p15, 0, r0, c7, c10, 1
    add r0, r0, #32
    cmp r0, r1
    blo 5b
    dsb sy
    mov r0, #0
    mcr p15, 0, r0, c7, c5, 0
    mcr p15, 0, r0, c7, c5, 6
    dsb sy
    isb sy
    bx lr
.ltorg
.balign 4
relocated_end:
.org 0x1000
native_image:
    .incbin "openiboot-native.bin"
native_image_end:
.balign 4
loader_image:
    .incbin "t4-oib-loader.bin"
loader_image_end:
.section .note.GNU-stack,"",%progbits
