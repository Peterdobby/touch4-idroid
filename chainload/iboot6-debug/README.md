# Controlled live iBoot6 entry assessment

The user confirmed that the existing DRV6 chain only starts iOS7 automatically;
there is no existing interactive iBoot6 debug session. The prior real-device
success remains the isolated CPU/loader experiment, not a complete live iBoot6
or DRV6 handoff.

Upstream `De-Rebus-Antiquis-v6/iBootDebugger/main.c` uses the Apple certificate
area for breakpoint code and renames boot environment strings. It was inspected
but not built or run: that is outside the requirement to preserve verification
logic. Its exploit-specific breakpoint workflow is not needed for this project.

A smaller debug candidate has been prepared on the host only. In exact N81
10B500 firmware, offset `0x42000` points to the string `fsboot` and offset
`0x42004` contains its handler `0x5ff00ae5`. The candidate changes that single
word to the live loader's ARM entry at `0x44000000`. Every other byte is checked
to remain identical, including signature-verification code, certificate data,
boot variable strings and native cleanup routines. This is normal RAM debug
dispatch instrumentation; no exploit source is changed or compiled.

```sh
cd .
python3 chainload/iboot6-debug/prepare.py
```

Output `build/iboot6-ram-debug/iBoot6-fsboot-debug-CANDIDATE.raw` is **not** a
verified debugger, installer, ready hardware test or complete boot path. Do not
send it using a guessed DFU/Recovery command. A signature-enforcing image loader
would still reject an unauthorized modified image; no signature bypass is added.
It requires external staging inside the already-controlled RAM environment.

The remaining checks are recorded in `build/iboot6-ram-debug/ASSESSMENT.json`:
prove the automatic boot call path, rule out persistent writes during preceding
initialization, verify full iBoot6 relocation/entry/mapping, and establish the
controlled RAM upload/handoff. These checks must precede hardware execution.
Redirecting fsboot does not by itself prevent earlier storage/NVRAM activity.
No new hardware boot command is claimed until those dependencies are resolved.

Original project, known-good Android, original firmware and existing DRV6 chain
were not modified. No device or persistent storage operation is performed by
this preparation script.
