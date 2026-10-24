.syntax unified
.cpu cortex-a8
.thumb
.text
.global _start
.thumb_func
_start:
    movs r0, #0
    movs r1, #0
    movs r2, #0
    movs r3, #0
    ldr r12, =0x41000000
    bx r12
.ltorg
.org 0x20
.thumb_func
native_bridge:
    mov r12, r1
    movs r0, #0
    movs r1, #0
    movs r2, #0
    movs r3, #0
    bx r12
.section .note.GNU-stack,"",%progbits
