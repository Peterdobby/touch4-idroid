/* ARM-only veneers. B, rather than BL, preserves original LR at inline sites.
 * Save all registers and condition flags; keep stack eight-byte aligned.
 */
.syntax unified
.cpu cortex-a8
.arm
.text
.global t4_zimage_probe,t4_before_cache,t4_before_enable,t4_after_enable
t4_zimage_probe: b header_probe
t4_before_cache: b cache_probe
t4_before_enable: b enable_probe
t4_after_enable: b enabled_probe
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
probe cache_probe,10
    /* Emulate original BL cache_on at 0x64. */
    ldr lr,=0x02000068
    ldr pc,=0x020001a0
.ltorg
probe enable_probe,11
    /* Original conditional DACR write at 0x314; flags were restored. */
    mcrne p15,0,r1,c3,c0,0
    ldr pc,=0x02000318
.ltorg
probe enabled_probe,12
    /* At 0x328, original SCTLR read-back and instruction barrier already ran.
     * Screen routine intentionally halts instead of original mov pc,ip.
     */
1:  b 1b

.global t4_branch_linux
.type t4_branch_linux,%function
t4_branch_linux:
    cpsid if
    mov ip,r0
    mov r0,#0
    bx ip
