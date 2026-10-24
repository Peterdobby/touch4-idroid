/* ARM diagnostic vectors. Inline hooks use B to preserve LR and all flags. */
.syntax unified
.cpu cortex-a8
.arm
.section .text.t4vectors,"ax",%progbits
.global t4_zimage_probe,t4_after_enable,t4_before_decompress,t4_after_decompress
.global t4_putstr,t4_before_kernel
.global t4_core_entry,t4_processor_ok,t4_atags_pages,t4_mmap_switched
.global t4_early_c,t4_printk_returned
.global t4_start_native_console
t4_zimage_probe: b header_probe
t4_after_enable: b enabled_probe
t4_before_decompress: b decompress_probe
t4_after_decompress: b decompressed_probe
t4_putstr: b putstr_probe
t4_before_kernel: b kernel_probe
t4_core_entry: b core_probe
t4_processor_ok: b processor_probe
t4_atags_pages: b atags_pages_probe
t4_mmap_switched: b switched_entry
t4_early_c: b early_c_probe
t4_printk_returned: b printk_probe
t4_start_native_console: b native_console_entry
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
probe core_probe,16
    msr cpsr_c,#0xd3
    mrc p15,0,r9,c0,c0,0
    ldr pc,=0x00008008
.ltorg
probe processor_probe,17
    /* C refuses r5==0. Replay MOVS; original BEQ therefore not taken. */
    movs r10,r5
    ldr pc,=0x00008014
.ltorg
atags_pages_probe:
    ldr lr,=atags_return
    ldr pc,=0x00008138
.ltorg
probe atags_return,18
    ldr lr,=pages_return
    ldr pc,=0x0000804c
.ltorg
probe pages_return,19
    ldr lr,=0x0000802c
    ldr pc,=0x0000802c
.ltorg
switched_entry:
    /* r13 is a virtual branch target, not a stack, at __mmap_switched entry.
     * All other registers survive; restore its original value before replay.
     */
    ldr sp,=0x44010000
probe switched_probe,20
    ldr sp,=0xc0008180
    ldr r3,=0xc00081c8
    ldmia r3!,{r4-r7}
    ldr pc,=0xc0008188
.ltorg
probe early_c_probe,21
    ldr lr,=debug_objects_return
    ldr pc,=0xc0014de0
.ltorg
debug_objects_return:
    cpsid i
    ldr lr,=0xc0008600
    ldr pc,=0xc0008604
.ltorg
probe printk_probe,22
    /* Tail-call with the ORIGINAL return address: helper mappings disappear
     * during paging_init, so setup_arch must never return into this module. */
    add r0,sp,#12
    ldr lr,=0xc0008658
    ldr pc,=0xc000b1f0
.ltorg
probe native_console_entry,23
    /* Save every incoming register, including LR, across the extra native call.
     * Its return is still before paging_init, while helper mappings exist. */
    push {r0-r12,lr}
    mrs r0,cpsr
    push {r0,r1}
    ldr lr,=native_console_return
    ldr pc,=0xc000d8ec
.ltorg
native_console_return:
    pop {r0,r1}
    msr cpsr_f,r0
    pop {r0-r12,lr}
probe native_console_ready,24
    /* Replay the displaced PC-relative LDR and BL sanity_check_meminfo. */
    ldr r7,=0xc000b7fc
    ldr r7,[r7]
    ldr lr,=0xc000b5a8
    ldr pc,=0xc000ca78
.ltorg
.global t4_branch_linux
.type t4_branch_linux,%function
t4_branch_linux:
    cpsid if
    mov ip,r0
    mov r0,#0
    bx ip
