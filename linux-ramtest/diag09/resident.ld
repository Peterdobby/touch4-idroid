PHDRS { ram PT_LOAD FLAGS(7); }
SECTIONS {
    . = 0xc3e00000;
    .text : { KEEP(*(.text.t4vectors)) *(.text*) } :ram
    .rodata : { *(.rodata*) } :ram
    .data : { *(.data*) } :ram
    . = ALIGN(4);
    .bss (NOLOAD) : { *(.bss*) *(COMMON) } :ram
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) }
}
