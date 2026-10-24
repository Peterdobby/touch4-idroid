# T4_OIB_CHAINLOAD_01

Standalone loader: `build/chainload/t4-oib-loader.bin` (12 bytes).
It branches from ARM address `0x44000000` to an already staged, **unchanged**
`build/phase1-published/openiboot-native.bin` at `0x41000000`.
No exploit, USB stack, storage access, signature patch, or Android code is linked
into the loader. No files in the Android or phase1 implementations are modified.

## Build and verify

From `.`:

```sh
python3 chainload/build.py
build/t4-arm-tests-venv/bin/python3 chainload/test-arm.py
python3 chainload/run.py --check
```

The build uses the existing local ARM GCC 4.8 toolchain, host C compiler,
libirecovery and local static libusb. Offline ARM tests use the existing Unicorn
environment. Rebuilding never runs any exploit or accesses USB.

## Existing controlled RAM environment test

For an **already controlled N81 BootROM DFU**, using the unchanged, existing
4.1 iBSS file:

```sh
python3 chainload/run.py --boot
```

If that exact 4.1 go iBSS is **already running** in controlled Recovery:

```sh
python3 chainload/run.py --boot --ibss-already-running
```

These commands do not turn ordinary DFU into a controlled environment. They do
not call ipwnder or other exploit tools. Do not use the Recovery option on an
arbitrary stock Recovery/iOS6 iBoot. The fixture also checks SVC mode and the
pinned iBSS function prefix at runtime, before staging anything.

The existing Recovery transport has one fixed RAM download/go address. Therefore
the **separate external placement fixture**, not the 12-byte loader itself,
stages the two files in RAM and executes the actual standalone loader:

```text
existing iBSS download/go 0x41000000
 → RAM placement code relocated to 0x44001000
 → unchanged native image copied to 0x41000000
 → 12-byte loader copied to 0x44000000
 → loader → native wrapper → existing iBSS jump_to → OpeniBoot
```

Scratch RAM `0x44000000..0x44002000` must be free and identity-accessible in the
controlled context. The fixture makes code/data coherent without changing MMU,
cache enable bits or interrupt masks. This address mapping and real cache effects
remain subject to hardware verification; emulator success does not establish them.

In any other debugger, place the native image and loader at their stated addresses,
make uploaded code coherent, preserve the live pinned iBSS context and enter the
loader in ARM privileged mode. The loader itself performs no upload or copy.

## Hardware success and failure

Success requires all three new outputs:

```text
OpeniBoot USB 0525:1280 opened.
openiboot 0.3 commit c5cee8c for iPod Touch 4G
CHAINLOAD_USB_VERSION_CONFIRMED
```

The host first rejects an already present OpeniBoot device to avoid claiming an
old session as a new boot. It then sends `version`, requiring its fresh start,
exact version string, and successful completion. It never sends install, erase,
filesystem, NAND/NOR, NVRAM or partition commands.

`build/chainload/logs/*.json` records the actual hardware result; upload completion,
offline checks and emulation are never labelled successful hardware boots.
`manifest.json` describes the build, not a hardware result.

If the fixture rejects mode/version, it returns `r0=0xe001` to the existing caller,
without copying the image. A missing USB response alone cannot distinguish this
guard from a later failure; a debugger must inspect the return/code location.

## Preserved baseline

Full frozen archive (created and fully verified before this task):

`../project-archives/touch4-idroid-TOUCH03-known-good-20261023/`

The archive has write bits removed. This build rechecks its original manifest
SHA-256 and compares 12 protected live inputs against archived bytes, including
the working Android kernel/initramfs/touch service and existing OpeniBoot/iBSS.
See `build/chainload/known-good-archive.json` for the previous full verification
and this build's independent checks. It does not claim to rehash the entire 14GB
archive on every rebuild.

Full address and CPU contract: [CONTRACT.md](CONTRACT.md).
