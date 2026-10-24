ENTRY(_start)
SECTIONS {
    . = 0x41000000;
    .text : { *(.text.entry) }
    /DISCARD/ : { *(.comment) *(.ARM.attributes) *(.note*) }
}
