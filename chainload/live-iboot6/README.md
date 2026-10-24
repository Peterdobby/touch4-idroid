# T4_LIVE_IBOOT6_01

Build and offline ABI/guard test:

```sh
cd .
python3 chainload/live-iboot6/build.py
build/t4-arm-tests-venv/bin/python3 chainload/live-iboot6/test-arm.py
```

Artifact: `build/chainload-live-iboot6/t4-oib-live-iboot6.bin`, ARM entry at
`0x44000000`. **Requires live, controlled N81 10B500 iBoot-1537.9.55.**
Do not boot this file using phase1/iBSS: that environment does not supply the
live firmware and globals required by the new native jump routine.

This candidate verifies 16-byte native jump and CPU function prefixes, then calls
the running iBoot's original native jump function at `0x5ff1cef1`, passing
`(0, 0x44000100, 0, 0)`. The callback receives control only after that routine's
existing platform cleanup, critical section and CPU quiesce. It then copies the
frozen native image to `0x41000000`, adapts only the RAM wrapper target to
`0x44000201`, and enters the original raw ARM payload with r0-r3 zero.

The exact native jump disassembly is saved as `jump-to.disasm`. Its CPU-quiesce
call is at `0x5ff1cf16`, callback BLX at `0x5ff1cf26`. Full dependencies of the
preceding four platform callbacks remain unverified on real hardware. The
candidate itself has no storage/USB/exploit/persistence implementation.

Both `0x44000000` (uploaded code/data) and `0x5ff00000` (live firmware) must be
accessible in the debug context, and callback code must remain mapped after
quiesce. A valid live stack and coherent uploads are required. Prefix checks
cannot make an unmapped firmware address safe to read; use the candidate only
after identifying the actual running iBoot and memory mappings.

**Missing real-device prerequisite:** a controlled live iBoot6 debug entry.
The current source tree contains the decrypted stock firmware and an isolated
CPU test, but no ready-to-use controlled iBoot6 USB debug image was found.
Ordinary Recovery is insufficient. Its existing `go` handler at `0x5ff01131`
parses an iBEC image through the image-loading path; it is not an arbitrary
`jump 0x44000000` command. Therefore no guessed `irecovery -f raw.bin -c go`
command is supplied.

The next genuine hardware test must use an **existing** controlled iBoot6 debugger
to stage the candidate at `0x44000000`, make instructions coherent, and invoke its
ARM entry with the live context intact. Once the debugger and its transport are
identified, its exact upload/invoke commands can be supplied. No exploit,
signature-check modification, NVRAM change or persistent installation was made
to obtain such an entry during this work.

Offline tests execute the original native jump wrapper and CPU shutdown plus
the compiled candidate. **Four platform cleanup callbacks are explicitly mocked**
with Thumb `bx lr` in emulator memory only. They check ABI/guards, not real
peripheral teardown. Wrong firmware prefix and user-mode cases return `0xe601`
without writes. `ARM-TESTS.json` explicitly records these limits.

Real success still requires a new USB `0525:1280` and fresh ACM version round trip.
After invoking from the real debugger, the existing host verifier is:

```sh
build/chainload/acm-version
```

No hardware or untethered success is claimed by building or emulating this file.
