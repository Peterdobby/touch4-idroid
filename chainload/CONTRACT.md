# Exact N81 RAM chainload contract

This implementation applies to the existing controlled **N81 4.1 / 8B117 iBSS**
context. It is not a generic iOS6 iBoot port. The attached broader persistent-boot
proposal was treated as background; none of its persistence or exploit work is
part of this implementation.

## Successful existing phase1 path

`phase1/run.py` validates the native header and pinned iBSS hash, verifies the
target CPID/BDID/ECID, and calls the phase1 transport. That old script can invoke
an external exploit tool if DFU is not controlled. The new chainload runner does
**not** call that script or the exploit tool.

`phase1/load.c:57–77` requires already controlled BootROM DFU, uploads the existing
iBSS with `IRECV_SEND_OPT_DFU_NOTIFY_FINISH`, reconnects Recovery, sends the native
image with `IRECV_SEND_OPT_NONE`, then sends the existing `go\0` USB control request
(`0x40`, request/value/index all zero). Its upload return value is not proof of boot.

`build/ibss-go-patch.json` records the preexisting fixed `go` handler address
`0x41000000`. That file and iBSS are read-only inputs here; no patch is generated.
`tools/native_image.py` and `phase1/native_jump.S` confirm the native placement.

## Frozen image layout

| Item | Exact value |
|---|---|
| Input | `build/phase1-published/openiboot-native.bin` |
| Size | 282624 / `0x45000` bytes |
| SHA-256 | `890de9dbf62a25226049d43d3265020f8fa97ae8035264a5a7c4ec67304b1715` |
| Whole-image load/entry | `0x41000000`, ARM |
| Wrapper span | offsets `0x0000..0x0fff` |
| Raw payload offset/entry | `0x1000` / `0x41001000`, ARM |
| Raw payload length | 276384 / `0x437a0` bytes |
| Raw SHA-256 | `cd32dbac3d10a81b64226ffa4057fa8e202e699e3ff2182a7560eea077d5fbe1` |
| Tail span/length | `0x447a0..0x44fff` / 2144 (`0x860`) bytes |
| Section/image alignment | `0x1000` from existing GNU assembler packaging |
| Native jump function | `0x8401496d` Thumb (`0x8401496c` code address) |

The version string is present in the frozen raw bytes. It must still be returned
over a real `version` command for the current test to count as hardware success.

The 28-byte launcher is exactly:

```asm
mov r0, #0
ldr r1, =0x41001000
mov r2, #0
ldr r3, =0x8401496d
bx r3
/* literals: 0x41001000, 0x8401496d */
```

Then nine ARM NOP words and zero fill extend to offset `0x1000`. The complete image
is copied unchanged; wrapper, payload and tail all remain byte-identical.
No `0x2000` USB alignment requirement is inferred.

## Proven CPU handoff and remaining dependencies

The local evidence is disassembly of pinned `build/iBSS.n81ap.raw`, not a guess
based on another iBoot version:

* `build/native-wrapper-evidence/jump-to.txt`: `0x8401496c` saves the callback and
  arguments, calls existing helpers `0x8401488c`, `0x84013940`, `0x840139e8`, enters
  the critical-section helper `0x84014dfc`, calls CPU shutdown `0x8401614c`, then
  calls the raw ARM entry through `BLX r6`, with **r0=r1=r2=r3=0**.
* `irq-disable.txt`: the critical-section path calls `0x84000584` to set CPSR.I
  when entering its outermost critical section. This evidence does not establish
  an unconditional FIQ mask. Keep the live bootloader's nesting/global state.
* `cpu-shutdown.txt`: reads ACTLR and clears `0x100`, cleans the data cache, then
  applies SCTLR mask `0xffffe7fa` (clearing M/C/Z/I), sets A (`0x2`), clears U
  (`0x00400000`) and writes SCTLR. Thus MMU, D-cache, I-cache and branch prediction
  are disabled before entering the raw image.
* `cache-clean.txt`: set/way data-cache maintenance across four ways, `0x2000`
  index range in `0x40` steps, followed by the existing synchronization operation.

The first three helper identities and all their live global dependencies have
not been exhaustively reconstructed. Consequently the contract requires the
**live, working pinned iBSS environment**, including its privileged mode, valid
stack and mappings. Merely copying its jump function into another environment
would not satisfy this contract. No such copy or patch is performed.

The standalone loader is two ARM instructions and one literal:

```asm
ldr ip, [pc]      /* literal at loader+8 */
bx ip
.word 0x41000000
```

It changes only `r12` and PC; it preserves SP, LR, CPSR, IRQ/FIQ masks and CP15
state, performs no memory writes and never returns. It therefore needs coherent,
already staged native bytes at `0x41000000` and readable/executable mappings for
itself, native image and existing iBSS. It does not independently shut down the
CPU before the proven wrapper, avoiding an unverified virtual/physical transition.

The test placement fixture is deliberately separate. It accepts SVC ARM entry
only, verifies 16 bytes at the pinned jump function, then copies its own small
placement code to `0x44001000` before overlapping the original download buffer.
It forward-copies native bytes from `0x41001000` down to `0x41000000` (safe because
destination precedes source), places the standalone loader at `0x44000000`,
cleans modified D-cache lines to PoC by MVA, invalidates I-cache/branch predictions
and branches to the loader. It does not change cache enable bits, MMU or IRQ
masks. Scratch-RAM accessibility and physical cache behaviour need real testing.

## OpeniBoot's own entry

`research/openiBoot-c5cee8c/arch-arm/entry.sx:73–129` contains the A4 MIU setup
(`0xBFC00000`, low bits set to 2), relocation to `_start=0`, cache maintenance and
branch to the relocated entry. Lines 131–166 clear BSS, set exception/SVC stacks,
and enter `OpenIBootStart`. A4 RAM/heap addresses are defined in
`plat-a4/includes/hardware/a4.h`. All this remains in the original native image.
The loader contains no display, menu, USB, Android or NAND implementation.

## Validation boundaries

`ARM-TESTS.json` executes the compiled 12-byte loader with four IRQ/FIQ mask
combinations, tests the unchanged wrapper's arguments and ARM-to-Thumb branch,
and executes the real placement fixture through the actual loader to existing
iBSS jump entry. It verifies byte-exact native placement, unchanged iBSS, allowed
RAM-write ranges, and no writes when rejecting user mode/wrong iBSS prefix.
Cache-maintenance instructions are executed by the emulator without skips, but
physical cache effects and real MMU mapping are not emulated hardware evidence.
These tests stop before the live iBSS cleanup and OpeniBoot hardware initialization.

Only a new `0525:1280` enumeration followed by a completed fresh ACM `version`
round trip can pass the requested real-device test. Results belong in
`build/chainload/logs/`; a build manifest or emulator pass never proves that boot.
