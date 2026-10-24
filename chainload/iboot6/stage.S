/* Isolated RAM compatibility test. Entered through unchanged iBSS wrapper.
 * The original iBSS cleanup has already run: this is not a live iBoot6 session.
 */
.syntax unified
.cpu cortex-a8
.arm
.text
.global _start, cpu_image, cpu_end, loader_image, loader_end
_start:
    cpsid if
    ldr r0, =cpu_image
    ldr r1, =0x43000000
    ldr r2, =cpu_end
1:
    ldr r3, [r0], #4
    str r3, [r1], #4
    cmp r0, r2
    blo 1b
    ldr r0, =loader_image
    ldr r1, =0x44000000
    ldr r2, =loader_end
2:
    ldr r3, [r0], #4
    str r3, [r1], #4
    cmp r0, r2
    blo 2b
    dsb sy
    mov r0, #0
    mcr p15, 0, r0, c7, c5, 0
    dsb sy
    isb sy
    ldr sp, =0x44000e00
    ldr r3, =0x4301eb81
    blx r3
    dsb sy
    isb sy
    ldr r12, =0x44000000
    bx r12
.ltorg
.balign 0x1000
cpu_image:
    .incbin "iboot6-cpu-only.bin"
cpu_end:
.balign 0x1000
loader_image:
    .incbin "t4-oib-iboot6-loader.bin"
loader_end:
.section .note.GNU-stack,"",%progbits
