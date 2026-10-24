/* GPL-2.0-or-later. ARM probe occupies the fixed start of this RAM module.
 * Linux zImage's first three NOPs branch here. Preserve all incoming regs.
 */
.syntax unified
.cpu cortex-a8
.arm
.text
.balign 4
.global t4_zimage_probe
.type t4_zimage_probe,%function
t4_zimage_probe:
    push {r0-r12,lr}
    mov r0,sp
    bl t4_zimage_probe_screen
    pop {r0-r12,lr}
    ldr pc,=0x0200000c
.ltorg
.size t4_zimage_probe,.-t4_zimage_probe

.global t4_branch_linux
.type t4_branch_linux,%function
t4_branch_linux:
    cpsid if
    mov ip,r0
    mov r0,#0
    bx ip
.size t4_branch_linux,.-t4_branch_linux
