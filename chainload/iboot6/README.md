# T4_IBOOT6_RAM_01 — isolated CPU/loader compatibility experiment

```sh
cd .
python3 chainload/iboot6/build.py
build/t4-arm-tests-venv/bin/python3 chainload/iboot6/test-arm.py
python3 chainload/iboot6/run.py --check
```

Enter hardware DFU, then:

```sh
python3 chainload/iboot6/run.py --boot
```

This command reuses **unmodified** `phase1/run.py`, including its existing external
DFU tool when necessary. It creates/modifies no exploit, signature patch,
NVRAM, NOR/NAND, filesystem or persistent boot-chain component on the device.
The known-good Android and published OpeniBoot inputs are pinned and unchanged.

Outputs:

* `build/chainload-iboot6/t4-oib-iboot6-loader.bin`: ARM post-quiesce candidate
  linked at `0x44000000`, with frozen native bytes embedded at offset `0x1000`.
* `build/chainload-iboot6/iboot6-ram-test-native.bin`: boot this **test image** via
  the existing iBSS RAM workflow. Do not directly boot the candidate through phase1.

Test path:

```text
existing DFU/iBSS → existing native CPU cleanup → test stage
 → unchanged iBoot6 CPU-only instructions in RAM at 0x43000000
 → post-quiesce loader at 0x44000000
 → native RAM copy at 0x41000000
 → Thumb ABI bridge at 0x44000201
 → original OpeniBoot raw entry at 0x41001000
```

Only three audited ranges are taken from the existing public N81/10B500 firmware
SHA256 `d167d3303354296121da953ba8df62755f902932fccb8fdb29232bba1d057bda`:
`0x410..0x437` CP15 helpers, `0x1e61c..0x1e64b` cache clean, and
`0x1eb80..0x1ebaf` CPU quiesce. Everything else in the sparse CPU blob is zero.
These routines use relative calls to the copied helpers, no live iBoot globals,
platform callbacks or peripheral operations. Source instruction bytes are unchanged.
The sibling project's build scripts and exploit sources are never executed.

The source native image is byte-identical to the working published binary.
After CPU shutdown, the loader copies it to RAM and changes **only** the wrapper
literal at `0x41000018` from `0x8401496d` to its own Thumb bridge `0x44000201`.
The raw payload and tail are byte-identical. No original iBSS RAM code is patched.
The bridge passes r0–r3=0 and enters the raw payload in ARM mode, matching the
existing iBSS entry ABI. Cache/MMU enable bits must already be clear; otherwise
the candidate halts. CPSR/SCTLR are recorded at `0x44000f00/+4` for a debugger.

**Limits:** the initial iBSS workflow has already quiesced the CPU. Executing the
iBoot6 routines again tests their instruction path, candidate relocation and
adapted wrapper, not shutdown from a live iBoot6 cache/MMU/peripheral state.
This test does not run a full iOS6 iBoot, DRV6 or cold boot. A successful result
cannot be labelled untethered success. The later live iBoot6 experiment still
needs a controlled debug entry and proof of its RAM mappings/peripheral cleanup.

Success for this test requires a new USB `0525:1280` enumeration and an actual
completed `version` returning `openiboot 0.3 commit c5cee8c for iPod Touch 4G`,
then `CHAINLOAD_USB_VERSION_CONFIRMED`. Results/logs are saved in
`build/chainload-iboot6/logs/`. Photograph the screen if the test does not enumerate.

No device test has been claimed by compilation or emulation. The ARM test executes
all CPU/loader instructions without instruction substitutions or skips and checks
entry ABI, write ranges, unchanged raw bytes and unchanged original iBSS memory.
Physical cache effects and live mappings require hardware.
