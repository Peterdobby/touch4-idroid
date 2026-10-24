.syntax unified
.cpu cortex-a8
.arm
.section .text.t4vectors,"ax",%progbits
.global resident_io_entry,resident_board_entry,resident_reserve_entry
.global resident_gate_entry
.type resident_io_entry,%function
resident_io_entry: b resident_iotable
.type resident_board_entry,%function
resident_board_entry: b resident_board_map
.type resident_reserve_entry,%function
resident_reserve_entry: b resident_reserve
.type resident_gate_entry,%function
resident_gate_entry: b resident_gate
.global resident_percpu_entry,resident_irq_entry,resident_fatal_entry
.type resident_percpu_entry,%function
resident_percpu_entry: b percpu_returned
.type resident_irq_entry,%function
resident_irq_entry: b irq_begin
.type resident_fatal_entry,%function
resident_fatal_entry: b resident_fatal
.global resident_memset_entry
.type resident_memset_entry,%function
resident_memset_entry: b memset_abi
.type memset_abi,%function
memset_abi:
    /* GCC's builtin rules require the ORIGINAL destination as return value.
     * Retain the original kernel implementation and all its fast paths. */
    push {r0,lr}
    uxtb r1,r1
    bl original_memset
    pop {r0,pc}
.type original_memset,%function
original_memset:
    /* Replay the displaced ANDS/BNE, and the original unaligned prelude.
     * The old prelude falls through the patched entry, so replay it here to
     * avoid re-entering the wrapper. Byte-count/condition rules unchanged. */
    ands r3,r0,#3
    beq memset_aligned
    subs r2,r2,#4
    blt memset_short
    cmp r3,#2
    strblt r1,[r0],#1
    strble r1,[r0],#1
    strb r1,[r0],#1
    add r2,r2,r3
memset_aligned:
    ldr pc,=0xc00e1528
memset_short:
    ldr pc,=0xc00e158c
.ltorg
.macro progress number
    push {r0-r12,lr}
    mrs r0,cpsr
    push {r0,r1}
    mov r0,#\number
    bl resident_progress
    pop {r0,r1}
    msr cpsr_f,r0
    pop {r0-r12,lr}
.endm
.type percpu_returned,%function
percpu_returned:
    progress 0
    /* Replay MOV r0,#0; BL build_all_zonelists from start_kernel. */
    mov r0,#0
    ldr lr,=0xc00086c0
    ldr pc,=0xc0134ddc
.ltorg
.type irq_begin,%function
irq_begin:
    progress 1
    /* Replay both original calls; resident addresses survive paging_init. */
    ldr lr,=irq_desc_returned
    ldr pc,=0xc000ff14
.ltorg
.type irq_desc_returned,%function
irq_desc_returned:
    progress 2
    ldr lr,=vic_returned
    ldr pc,=0xc000ae00
.ltorg
.type vic_returned,%function
vic_returned:
    progress 3
    ldr lr,=0xc000874c
    ldr pc,=0xc000874c
.ltorg
.global original_fb_reserve
.type original_fb_reserve,%function
original_fb_reserve:
    /* Replay original PUSH and PC-relative LDR, then its untouched body. */
    push {r3,lr}
    ldr r3,=0xc01a44a8
    ldr pc,=0xc000d8a4
.ltorg
