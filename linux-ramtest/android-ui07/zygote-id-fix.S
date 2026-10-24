.syntax unified
.cpu cortex-a8
.thumb
.text
.global t4_setregid_fix
.type t4_setregid_fix,%function
.thumb_func
t4_setregid_fix:
    push {r4,lr}
    movs r0,r2
    movs r1,r3
    blx setregid_plt
    cmp r0,#0
    beq 1f
    blx errno_plt
    ldr r0,[r0]
1:  pop {r4,pc}
.org 32
.global t4_setreuid_fix
.type t4_setreuid_fix,%function
.thumb_func
t4_setreuid_fix:
    push {r4,lr}
    movs r0,r2
    movs r1,r3
    blx setreuid_plt
    cmp r0,#0
    beq 2f
    blx errno_plt
    ldr r0,[r0]
2:  pop {r4,pc}
.org 64
