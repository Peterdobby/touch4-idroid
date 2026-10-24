/* t4-oib-loader v1: an already staged N81 native image, ARM entry.
 * RAM contract: chainload/CONTRACT.md. No stack, copies, CP15, MMIO or calls.
 * The frozen image's own wrapper invokes its pinned iBSS shutdown routine.
 */
.syntax unified
.cpu cortex-a8
.arm
.section .text.entry,"ax",%progbits
.global _start
.type _start,%function
_start:
    ldr r12, target
    bx r12
target:
    .word 0x41000000
.size _start, .-_start
.section .note.GNU-stack,"",%progbits
