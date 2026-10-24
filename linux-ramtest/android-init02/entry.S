/* ARM diagnostic vectors. Inline hooks use B to preserve LR and all flags. */
.syntax unified
.cpu cortex-a8
.arm
.section .text.t4vectors,"ax",%progbits
.global t4_zimage_probe,t4_after_enable,t4_before_decompress,t4_after_decompress
.global t4_putstr,t4_before_kernel
t4_zimage_probe: b header_probe
t4_after_enable: b enabled_probe
t4_before_decompress: b decompress_probe
t4_after_decompress: b decompressed_probe
t4_putstr: b putstr_probe
t4_before_kernel: b kernel_probe
.macro probe name, number
.balign 4
.global \name
.type \name,%function
\name:
    push {r0-r12,lr}
    mrs r0,cpsr
    push {r0,r1}
    add r0,sp,#8
    mov r1,#\number
    bl t4_head_probe_screen
    pop {r0,r1}
    msr cpsr_f,r0
    pop {r0-r12,lr}
.endm
probe header_probe,9
    ldr pc,=0x02000020
.ltorg
probe enabled_probe,12
    /* Replay original zImage+0x328 return, following its unchanged ISB. */
    mov pc,ip
probe decompress_probe,13
    /* Replay original BL decompress_kernel at zImage+0x160. */
    ldr lr,=0x02000164
    ldr pc,=0x02000b0c
.ltorg
probe decompressed_probe,14
    /* Replay original BL cache_clean_flush at zImage+0x164. */
    ldr lr,=0x02000168
    ldr pc,=0x02000620
.ltorg
probe putstr_probe,30
    /* Complete replacement of diagnostic text output, not the decompressor. */
    bx lr
probe kernel_probe,15
    mov r1,r7
    mov r2,r8
    ldr pc,=0x02000178
.ltorg
.global t4_branch_linux
.type t4_branch_linux,%function
t4_branch_linux:
    cpsid if
    mov ip,r0
    mov r0,#0
    bx ip
