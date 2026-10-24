.syntax unified
.cpu cortex-a8
.thumb
.section .entry,"ax",%progbits
.global t4_fs_entry
.thumb_func
t4_fs_entry:
    b.w t4_fsboot
.section .native_start,"ax",%progbits
.global t4_native_start
.thumb_func
t4_native_start:
    movs r0, #0
    movs r1, #0
    movs r2, #0
    movs r3, #0
    ldr r12, =0x41000000
    bx r12
.ltorg
.section .native_bridge,"ax",%progbits
.global t4_native_bridge
.thumb_func
t4_native_bridge:
    mov r12, r1
    movs r0, #0
    movs r1, #0
    movs r2, #0
    movs r3, #0
    bx r12
.section .note.GNU-stack,"",%progbits
