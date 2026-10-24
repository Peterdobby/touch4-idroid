# T4 untethered OpeniBoot 02

This experiment uses the existing, unchanged N81 DRA partition. It prepares a
normal Apple-signed 6.1.6 LLB, stock iBoot6, stock N81 device tree, startup and
recovery logos, the previously RAM-tested OpeniBoot second-stage loader, and
Apple's APTicket in the Kit's SCAB container. Charging artwork is omitted from
the minimum cold-boot set. No system/data filesystem, GPT, NVRAM, exploit,
signature-check routine or known-good Android/OpeniBoot source is modified.

The owner cancelled iOS recovery and authorized direct untethered testing.
`apply.py --apply` **writes persistent boot firmware**. It is not a RAM test.
It submits the LLB with selector 0, followed by six images with selector 1 on
the same AppleImage3NORAccess connection. It must never be used to append just
one unsigned image. It also must not be run a second time without inspecting
the existing attempt record. A zero API result alone is not boot success.

The Apple-issued ticket is for ECID YOUR_DEVICE_ECID / iPod4,1 / n81ap / 10B500.
The running 10B500 kernel accepted the personalized LLB through selector 2
before any update calls. The encrypted LLB DATA is unchanged. Personalization
follows [idevicerestore's IMG3 format handling](https://github.com/libimobiledevice/idevicerestore/blob/master/src/img3.c);
the LLB-first image ordering also matches its
[NOR image collection](https://github.com/libimobiledevice/idevicerestore/blob/master/src/restore.c)
and the local Bootlace `opibFlashManifest` implementation. The device DRA
partition is checked against its earlier verified 512 KiB hash, not rebuilt.

Host sources: this directory. Outputs and the exact test state:

- `build/untethered-oib-02/MANIFEST.json`: image hashes and selected order.
- `BUILD-SET.json`: package and ARM helper hashes.
- `OFFLINE-TESTS.json`: mock API order/CRC/truncation/argument tests only.
- `APPLY-ATTEMPT.json`: actual device API and subsequent boot observations.
- `logs/`: actual update output, NVRAM comparison, and USB version response.

Read the actual attempt record for success/failure. Do not infer a successful
cold boot from prepared files, mock tests, signature preflight or API returns.
An observed reboot into OpeniBoot without host payload upload establishes the
software-reboot path; an unplugged full power-cycle is a separate check.

Existing artifacts are protected from regeneration after an attempt. The
earlier single-image failed candidate remains separately marked failed.
