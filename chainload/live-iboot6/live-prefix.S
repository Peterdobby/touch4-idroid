/* Genuine LIVE iBoot6 context required. No firmware patch or exploit. */
    mrs r0, cpsr
    and r0, r0, #31
    cmp r0, #19
    bne wrong_live_context
    ldr r0, =0x5ff1cef0
    ldr r1, =jump_fingerprint
    mov r2, #16
1:
    ldr r3, [r0], #4
    ldr r12, [r1], #4
    cmp r3, r12
    bne wrong_live_context
    subs r2, r2, #4
    bne 1b
    ldr r0, =0x5ff1eb80
    ldr r1, =cpu_fingerprint
    mov r2, #16
2:
    ldr r3, [r0], #4
    ldr r12, [r1], #4
    cmp r3, r12
    bne wrong_live_context
    subs r2, r2, #4
    bne 2b
    /* Existing jump_to ABI: platform arg, callback, callback arg0, arg1. */
    mov r0, #0
    ldr r1, =post_quiesce
    mov r2, #0
    mov r3, #0
    ldr r12, =0x5ff1cef1
    bx r12
wrong_live_context:
    movw r0, #0xe601
    bx lr
.ltorg
jump_fingerprint:
    .incbin "jump-prefix.bin"
cpu_fingerprint:
    .incbin "cpu-prefix.bin"
.org 0x100
