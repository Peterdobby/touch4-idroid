/* Fixed ARM vector table precedes any compiler-generated cold text. */
PHDRS { ram PT_LOAD FLAGS(7); }
SECTIONS {
    . = 0x44000000;
    .text : { KEEP(*(.text.t4vectors)) *(.text*) } :ram
    .rodata : { *(.rodata*) } :ram
    .data : { *(.data*) } :ram
    . = ALIGN(4);
    .bss (NOLOAD) : { *(.bss*) *(COMMON) } :ram
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) }
}
