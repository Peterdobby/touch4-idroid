# T4_LINUX_DIAG_12: fix the native ARM memset return ABI

## Evidence

Photo <HOME>/Desktop/IMG_8184.jpeg shows repeated kmem_cache_node redzone errors
already inside kmem_cache_init. The payload has 27 bytes of 6b but its final byte remains 5a,
and the four-byte redzone is 5a instead of bb. SLUB FZPU exposed the problem earlier than DIAG10.
11 source/manifest/log/interpretation snapshots: experiments/linux-ram-11-memset-return/.

The current pinned kernel has native memset at C00E1520 in arch/arm/lib/memset.S.
It advances R0 through the destination, and both return paths leave the advanced R0 as return value.
The asm/string.h macro intends to return the original pointer, but GCC 4.8 recognizes the builtin
and reuses the native return value as the original pointer inside compiled init_object:

```
C007DA74: BL  C00E1520   ; fill object with 6b, length 27
C007DA78: MOV R3,R0     ; compiler expects ORIGINAL object here
```

Native memset actually returns object+27, so the A5 final byte is written at object+54 and
BB redzone at object+55..58 instead of object+27 and object+28..31. This is an independently
reproduced ABI incompatibility; no speculative hardware/DMA blame is needed.
Whether this alone resolves the DIAG10 later failure still requires hardware execution.

## Fix

Only the native memset first 8 bytes are additionally redirected in the decompressed RAM Image
at checkpoint 15 to a new ARM resident vector C3E0001C. The wrapper saves the original R0/LR,
truncates the fill int to an unsigned byte, calls the original native fill algorithm, and returns
with original R0 restored. The unaligned prelude is replayed without re-entering the patched entry;
the native aligned loop and short tail remain intact. No whole-kernel recompile/address shift.

Original zImage compressed input and initramfs remain identical. Native noalign, reserved RAM,
framebuffer/clock preservation, first-fatal halt, FZPU checks and NAND guards remain enabled.
The marker T4_MEMSET ORIGINAL_DEST_RETURN confirms the new board callback is executing.
All prior binary hashes 02 through 11 were checked unchanged. No device storage writes.

## Verification actually executed

- Unicorn 2.1.4 Cortex-A8 executes the original pinned ARM Image and reproduces its bad return.
- The exact compiled init_object reproduces the photo's missing A5/BB pattern with original code.
- The same init_object with patched memset produces A5 and BB at the correct offsets.
- 8288 actual ARM memset cases cover alignments 0..7; lengths 0..129 plus loop/page/65536 boundaries;
  fill bytes, negative int and high-bit int arguments; destination return, guard bytes, stack,
  callee-saved registers and CPU interrupt/mode state.
- All native hook boundaries/replay addresses, checksums, preserved NAND stubs and previous artifacts
  pass test_layout. Resident semantics and host --check pass.
- Hardware result for DIAG12 is pending. No PID1 success claim.

## User test

Enter hardware DFU, then:

```bash
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_12 --boot
```

Look for T4_LINUX_DIAG_12 in the command line. FZPU stays enabled; the repeated fresh-object
redzone failures should disappear if this fixes the observed fault on hardware.
If PID1_REACHED appears, photograph it. Otherwise photograph the first BUG or complete stopped
T4_FIRST_FATAL/T4_REG/T4_SLAB lines. Do not infer Android success from a host handoff message.

## Rebuild and ARM test

```bash
python3 linux-ramtest/diag12/build.py
python3 linux-ramtest/diag12/test_layout.py
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_12 --check
build/t4-arm-tests-venv/bin/python linux-ramtest/diag12/test_memset_arm.py
```

The local optional ARM test environment was created in build/t4-arm-tests-venv with
python3 -m venv and unicorn==2.1.4. It emulates RAM-only functions and does not access USB/MMIO.
