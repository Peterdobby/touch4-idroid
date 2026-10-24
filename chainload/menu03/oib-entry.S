/* RAM-test-only adapter from original OpeniBoot go to the already validated
 * post-quiesce loader. Exact iBoot6 ACTLR/SCTLR policy; no peripheral code.
 * Production iBoot calls the loader directly after its own native quiescence.
 */
.syntax unified
.cpu cortex-a8
.arm
.text
.global _start
_start:
    cpsid if
    mrc p15,0,r0,c1,c0,1
    bic r0,r0,#0x100
    mcr p15,0,r0,c1,c0,1
    mrc p15,0,r0,c1,c0,0
    ldr r1,=0xffbfe7f8
    and r0,r0,r1
    orr r0,r0,#2
    mcr p15,0,r0,c1,c0,0
    dsb sy
    isb sy
    ldr r12,=0x44000000
    bx r12
.ltorg
.section .note.GNU-stack,"",%progbits
