# T4_LINUX_DIAG_11: SLUB corruption diagnostics

## Confirmed hardware result from DIAG10

User photo: <HOME>/Desktop/IMG_8179.jpeg.
Displayed command line identifies T4_LINUX_DIAG_10. PERCPU, IRQ_DESC and VIC INIT all returned;
timer initialization, delay calibration and initcalls ran. SCTLR=10c5387d has A cleared.
First fatal: PC=c007ef2c LR=c0112700 CPSR=60000093 DFSR=00000005 DFAR=30363a34.
No PID1_REACHED observed.

The ELF identifies PC as kmem_cache_alloc+0x64, instruction E794C00C (LDR ip,[r4,ip]).
This reads get_freepointer_safe(s, object): *(void **)(object+s->offset), in mm/slub.c.
LR is con_insert_unipair+0x3c, immediately after the allocation in drivers/tty/vt/consolemap.c.
The picture lacks R4/R5/R12, so it cannot distinguish an invalid object from a corrupt offset,
and cannot identify the writer. CDMA startup before the failure is not proof CDMA caused it.

## Changes from DIAG10

- Add native slub_debug=FZPU command-line option. CONFIG_SLUB_DEBUG is already enabled.
  F: checks; Z: redzones; P: poisoning; U: allocation/free call-site tracking.
  Existing kernel setup_slub_debug processes this before kmem_cache_init creates caches.
  This changes allocator layout and timing for diagnosis; absence of failure alone does not prove a fix.
- Preserve the first-fatal halt; report R0 through R12 and SP in addition to PC/LR/CPSR/DFSR/DFAR.
- At the observed kmem_cache_alloc failure, report the cache, object and offset plus bounded RAM metadata.
  Addresses are checked for alignment and containment in the 256MB direct-mapped RAM bank;
  arbitrary faulting addresses and MMIO are not dereferenced.
- Shared command-line helper adds an optional build-time suffix, default empty; default output regression checked.
- Retain native noalign, display clock policy, NAND guards, all native call replay targets and reservations.
- No allocator code bypass, fabricated pointer repair, display/USB reinitialization, or driver replacement.

Original compressed Image, initramfs and all 02 through 10 binary hashes remain unchanged.
Changes are in the new RAM helper and supplied kernel arguments only. No device storage writes.
DIAG10 snapshots, log and interpretation: experiments/linux-ram-10-slub-fault/.

## User-run test

Enter hardware DFU, then:

```bash
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_11 --boot
```

Confirm the displayed command line contains T4_LINUX_DIAG_11 and slub_debug=FZPU.
Record the first BUG/cache report and Allocated/Freed information if shown, or all
T4_FIRST_FATAL, T4_REG and T4_SLAB lines at the stop. If output continues, record video.
PID1_REACHED from the RAM /init is still the userspace success criterion.
DIAG11 is built and offline checked; hardware outcome pending.

## Rebuild

```bash
python3 linux-ramtest/diag11/build.py
python3 linux-ramtest/diag11/test_layout.py
cc -Wall -Wextra -Werror linux-ramtest/diag11/test_resident.c -o build/T4_LINUX_DIAG_11/test-resident
build/T4_LINUX_DIAG_11/test-resident
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_11 --check
```
