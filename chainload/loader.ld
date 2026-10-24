ENTRY(_start)
SECTIONS {
    . = 0x44000000;
    .text : { *(.text.entry) }
    /DISCARD/ : { *(.comment) *(.ARM.attributes) *(.note*) }
}
