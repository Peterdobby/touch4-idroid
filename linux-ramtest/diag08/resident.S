.syntax unified
.cpu cortex-a8
.arm
.section .text.t4vectors,"ax",%progbits
.global resident_io_entry,resident_board_entry,resident_reserve_entry
.type resident_io_entry,%function
resident_io_entry: b resident_iotable
.type resident_board_entry,%function
resident_board_entry: b resident_board_map
.type resident_reserve_entry,%function
resident_reserve_entry: b resident_reserve
.global original_fb_reserve
.type original_fb_reserve,%function
original_fb_reserve:
    /* Replay original PUSH and PC-relative LDR, then its untouched body. */
    push {r3,lr}
    ldr r3,=0xc01a44a8
    ldr pc,=0xc000d8a4
.ltorg
