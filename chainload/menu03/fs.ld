ENTRY(t4_fs_entry)
SECTIONS {
  /* Audited unused alignment gap: text/const ends at 5ff41070, initialized
     data begins at 5ff42000. This survives native startup/BSS clearing. */
  . = 0x5ff41080;
  .entry : { *(.entry) }
  .text : { *(.text*) }
  .rodata : { *(.rodata*) }
  .data : { *(.data*) }
  .bss : { *(.bss*) *(COMMON) }
  _end = .;
  ASSERT(_end <= 0x5ff41fe0, "FS adapter exceeds unused image alignment gap")
  /DISCARD/ : { *(.native_start) *(.native_bridge) *(.ARM.exidx*) *(.ARM.extab*) *(.comment) }
}
