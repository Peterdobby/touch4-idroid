# DRV6 OpeniBoot second-stage candidate

## Failed hardware test — do not install

On 2026-10-24 the user authorized a persistent test. Submitting this candidate
with AppleImage3NORAccess selector 1 returned zero, but reboot entered DFU and
OpeniBoot USB did not appear. This is a failed test, not a working installer.
The single-image replacement semantics had not been established and the
installed original `ibob` had not been backed up. Do not repeat the write.

The exact attempt is recorded in
`build/drv6-stage2-candidate/backups/ramdisk-20261024-111128/WRITE-ATTEMPT.json`.
The original DRA partition was backed up, but that is not a backup of the
firmware image set. Recovery is pending the original custom IPSW/boot images
and a verified restoration procedure. System/data partitions remain readable
in the recovery ramdisk; that alone does not prove boot firmware is intact.
The remaining sections describe the earlier candidate preparation only.

This follows the existing Kit second-stage `ibob` image route. It reuses the
post-quiesce loader already observed reaching real OpeniBoot USB/ACM in the
isolated RAM experiment. It does not repeat the earlier DFU experiment or build
an exploit/debug iBoot. It creates no signature-check patch.

```sh
cd .
python3 chainload/drv6-stage2/prepare.py
```

Candidate output: `build/drv6-stage2-candidate/openiboot-stage2.ibob.img3`.
It is an unsigned Image3 `ibob` container whose DATA exactly matches the existing
post-quiesce ARM loader at `0x44000000`. The frozen native image is embedded
unchanged; the loader adapts only its RAM copy's wrapper jump target. Original
OpeniBoot and known-good Android files are protected and unchanged.

The existing DRA N81 payload changes the diags path to type `ibob`, image load
address `0x44000000`, and handler type zero. Stock function `0x5ff00908` then
calls native `jump_to` at `0x5ff1cef0` with the decoded image entry after loading.
This candidate is intended for that post-cleanup state, NOT the earlier
`t4-oib-live-iboot6.bin` that requires an already live initialized iBoot6.

This explains the proposed integration point; actual installed image type,
container compatibility, free boot-image capacity and a reversible update
method must come from the device backup. Do not replace any boot image using a
guessed NOR address. No installer is included yet, and no persistent write is
authorized by the original RAM-only restrictions.

## SSH ramdisk inventory

Enter your existing SSH ramdisk and supply the actual forwarded SSH port:

```sh
python3 chainload/drv6-stage2/collect-ramdisk.py --port 2222
```

Enter the ramdisk SSH password when prompted. The script confirms `iPod4,1`,
reads NVRAM/mounts/device nodes/tool names/device tree, and lists likely image
locations. It does not mount a filesystem, call an image updater, read an
unidentified raw storage device, write NVRAM, reboot or install. The inventory
is explicitly NOT labelled a boot-image backup; the real image read must be
selected after discovering the available ramdisk interfaces/tools.

Host outputs are in `build/drv6-stage2-candidate/backups/`. Any eventual install
must identify the exact changed image, preserve its original bytes and provide
the restoration method, then resolve the user's existing prohibition on NAND/NOR
and persistent writes. Preparing an unsigned candidate alone proves neither
acceptance by the installed chain nor successful cold boot.
