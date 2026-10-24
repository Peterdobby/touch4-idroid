# T4_ANDROID_INIT_04 — fix the false noalign panic before #23

Observed INIT03 hardware result: display remains at #22, between start_kernel printk and completion of setup_arch early parameters.

Root defect confirmed in the exact emitted ARM instructions: old get_cr() inline assembly is non-volatile. GCC 4.8 common-subexpression elimination replaces the second get_cr() with the first value saved in r4. Old t4_early_noalign clears A in noalign_setup(), then compares r4 against r4 & ~2. With A initially set, this necessarily calls panic even though hardware state was correctly changed.

Fix: native t4_read_control() uses asm volatile MRC plus a memory clobber. New instructions have two real MRC operations around noalign_setup(). Both saved control registers continue to be updated by the original kernel handler; all mismatch/U-bit guards remain.

Only kernel source delta against INIT02 is arch/arm/mm/mmu.c. INIT03 checkpoints/mappings/early console retained and relocated from new ELF. Initramfs and original Android init are byte-identical to INIT03. Storage stubs remain.

```sh
python3 linux-ramtest/android-init04/build.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-init04/test_noalign_arm.py
python3 linux-ramtest/android-init04/test_repair.py
python3 linux-ramtest/run.py --build T4_ANDROID_INIT_04 --check
```

From hardware DFU:

```sh
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_ANDROID_INIT_04 --boot
```

Expected next evidence: #23, native screen printk and T4_ALIGN before/after with only A bit cleared; eventually ANDROID_INIT_ENVIRONMENT_CONFIRMED and continuing service heartbeat. Actual hardware result remains pending. Emulator tests explicitly model CP15 reads/writes and execute the real handler instructions; they do not substitute for a device boot.

All device operations remain DFU/RAM-only; no persistent device writes.
