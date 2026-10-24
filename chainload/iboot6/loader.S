/* Post-quiesce ARM loader. No firmware/exploit/storage/USB implementation. */
.syntax unified
.cpu cortex-a8
.arm
.text
.global _start, native_image, native_end, halt, bridge, mailbox
_start:
    cpsid if
    ldr r10, =mailbox
    mrs r0, cpsr
    str r0, [r10]
    and r0, r0, #31
    cmp r0, #19
    bne halt
    mrc p15, 0, r0, c1, c0, 0
    str r0, [r10, #4]
    ldr r1, =0x1805
    tst r0, r1
    bne halt
    ldr r0, =native_image
    ldr r1, =0x41000000
    ldr r2, =native_end
1:
    ldr r3, [r0], #4
    str r3, [r1], #4
    cmp r0, r2
    blo 1b
    /* Adapt only the RAM copy's wrapper target. Never overwrite iBSS code. */
    ldr r0, =0x41000018
    ldr r1, =bridge
    str r1, [r0]
    dsb sy
    mov r0, #0
    mcr p15, 0, r0, c7, c5, 0
    dsb sy
    isb sy
    ldr r12, =0x41000000
    bx r12
halt:
    wfi
    b halt
.ltorg
.org 0x200
.thumb
.thumb_func
bridge:
    mov r12, r1
    movs r0, #0
    movs r1, #0
    movs r2, #0
    movs r3, #0
    bx r12
.org 0xf00
mailbox:
    .space 0x40
.org 0x1000
native_image:
    .incbin "openiboot-native.bin"
native_end:
.section .note.GNU-stack,"",%progbits
