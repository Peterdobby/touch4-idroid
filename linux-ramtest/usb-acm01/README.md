# T4_USB_ACM_01 — A4 USB probe repair, serial-only RAM test

Status: physical Linux ACM enumeration and bidirectional serial data confirmed
2026-10-20 from the user terminal and read-only macOS USB inventory.
See build/T4_USB_ACM_01/HARDWARE-RESULT.json. Tested payloads and the original
manifest remain byte-identical. Android/ADB are absent from this image.
The failed T4_ANDROID_USB_01 and all previous successful builds are preserved.

## Boot

Enter hardware DFU, then run:

```sh
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_USB_ACM_01 --boot
```

This deliberately starts minimal Linux/PID1, not Android. It keeps the inherited
framebuffer console, enables one g_serial CDC ACM port, and loads no adbd,
Android composite gadget, MTP, mass-storage or network gadget. Expected Linux
VID:PID is **0525:a4a7** (g_serial upstream default), distinct from the proven
OpeniBoot **0525:1280**. Do not use `adb devices` as this test's success criterion.

After Linux reaches PID1:

```sh
system_profiler SPUSBDataType
python3 tools/t4-acm-console.py --list
python3 tools/t4-acm-console.py --seconds 15
```

If multiple modem ports exist, append `--port /dev/cu.usbmodem…` with the exact
listed path. The program opens that port, asserts DTR/RTS, sends a test line,
and reports RAM_HEARTBEAT/HOST_ECHO. Nothing is installed or written to storage.
Expected: USB device appears, ACM opens, `T4_USB_ACM_01 RAM serial alive` and the
host test line arrive. A USB descriptor alone does not prove functioning data
endpoints. No real enumeration is claimed by the offline tests.

## Exact USB01 NULL root cause

Matched against `build/T4_ANDROID_USB_01/vmlinux` and its original driver object:

- PC **c013bb64**, `s3c_hsotg_enqueue_setup+0xc`.
- ARM instruction **e5d1300c**, `ldrb r3,[r1,#12]`.
- Previous instruction loads `r1=hsotg->ctrl_req` from `[r0,#0x30]`.
- Source `drivers/usb/gadget/s3c-hsotg.c:1284`, **req->zero = 0**.
- USB01 registers its IRQ before allocating ctrl_req, initializing endpoint
  queues/parents, enabling clocks, or resetting PHY/core. request_irq enables
  the line. Calling disable_irq immediately afterwards still leaves a race.
- With the observed unpowered-read fixture 0bad0add, actual USB01 probe + ISR
  instructions reproduce **PC c013bb64, LR c013c958, DFAR 0xc**:
  probe → request_irq → s3c_hsotg_irq → IN EP0 completion path
  (s3c_hsotg_epint, compiler-inlined) → enqueue_setup. The IN request is empty,
  so that path tries to queue the unallocated control request.

`usb01-fault-source.txt` maps the exact instruction to the C line using objdump
with DWARF. The driver was recompiled with -g into a separate object; its entire
.text was checked byte-identical to the original. The original kernel/objects
were never rebuilt. The photo's old first-fatal stop suppressed full registers
and unwind output; that missing physical dump cannot be recovered from a photo.
`irq-order-test.json` has **emulated** registers/trace, explicitly not a hardware
dump. The new first-fatal handler prints real registers, a bounded stack dump,
and backtrace before halting, with a recursion guard.

## Platform contract and minimal fix

The original struct s3c_hsotg_plat has only dma and is_osc, no PHY, regulator or
VBUS callbacks. Missing platform_data falls back to a zero static object (PIO),
so NULL platform_data itself is not this crash. clk_get("otg") checks ERR_PTR;
MEM resource/ioremap/IRQ errors are checked. ctrl_req and endpoint structures
were valid only later in probe, after the premature request_irq.

The new platform data explicitly selects PIO and supplies A4 callbacks for PHY,
post-core-reset settle, link pullup/session request, cleanup and snapshots.
Missing A4 callbacks refuse the Apple probe with ENODEV, rather than using the
Samsung PHY clock encoding. No dummy endpoint/request pointers are supplied.

`arch/arm/mach-s5l8930/a4-usb-glue.c` owns the Apple PHY/link operations.
`arch/arm/plat-samsung/dev-usb-hsotg.c` retains controller resource86100000/64KiB,
IRQ13, and binds that platform contract. Standard Linux clock references still
enable parent usbreg gate1d then child otg gate18. OIB explicitly enables18 then1d;
this ordering difference is recorded, not presented as measured equivalence.
Both gates are enabled before any PHY/core access; no extra clock MMIO path was
introduced alongside the existing clock framework.

Probe order now is:

1. Allocate state, map resource; initialize gadget and allocate real ctrl_req.
2. clk_enable("otg") and A4 PHY callback; validate readable core/config IDs.
3. Existing bounded DWC core reset; A4 1ms settle; capacity-checked FIFOs.
4. Initialize all endpoint queues, locks and parents.
5. Mask controller interrupts, acknowledge pending status, then request_irq.
6. Publish UDC. g_serial binds, queues EP0, then enables global interrupts and
   removes soft disconnect; A4 waits250us and sets GOTGCTL.SessionRequest.

The USB01 request_irq/disable_irq sequence is removed. No USB gadget-core,
serial-function, endpoint queue/transfer state-machine implementation is replaced.
USB01's bounded FIFO/reset errors and 1664-word FIFO allocation are retained.
The patch also returns ENOMEM on ctrl_req allocation failure and cleans platform
sysfs state/requests on failure/removal. All physical storage stubs and disabled
storage drivers remain verified by the builder.

## Hardware reference and register comparison

Canonical reference only:
`research/openiBoot-c5cee8c/plat-a4/usbphy.c`, its hardware header, and
`usb-synopsys/usb.c` / `usb-synopsys/includes/hardware/usb.h`.
See [REGISTER-COMPARISON.md](REGISTER-COMPARISON.md) for offsets, complete order,
actual recorded values, and fields still awaiting measurement. The published
OpeniBoot binary is unchanged. No speculative OIB measurement is filled in.

## Read the next screen

- USB_LNX_01: both clocks requested, actual gate registers and reference rate.
- USB_LNX_02 /03: PHY power / reset finished; USB_LNX_ID prints real GSNPSID and
  all four HWCFG registers. Sentinel/zero reads stop probe with ENODEV.
- USB_LNX_04_CORE_RESET: reset/idle wait returned, register snapshot.
- USB_LNX_05 EP_READY: real ctrl_req and endpoint state ready, IRQ not yet claimed.
- USB_LNX_06_PROBE_OK / U10: request_irq returned successfully.
- USB_LNX_07_EP0_READY /08_CONNECTED: gadget prepared and link attached. U20
  means g_serial bound, not host enumeration.
- USB_LNX_IRQ logs the first8 active status/mask pairs. PID1 prints U/IRQ/SET,
  ID, GINTSTS/GINTMSK/GOTGCTL/DCTL every5s. Rising SET plus host USB descriptors
  shows control transfers; opening ACM and receiving heartbeat/echo tests data.
- Failure: photograph the full last USB_LNX block or T4_FIRST_FATAL register/
  Call trace block. No extra waiting will recover a deliberate fatal halt.

## Rebuild / checks

```sh
python3 linux-ramtest/usb-acm01/build.py
build/t4-arm-tests-venv/bin/python linux-ramtest/usb-acm01/test_irq_order.py
build/t4-arm-tests-venv/bin/python linux-ramtest/usb-acm01/test_usb_arm.py
build/t4-arm-tests-venv/bin/python linux-ramtest/usb-acm01/test_bundle.py
python3 linux-ramtest/run.py --build T4_USB_ACM_01 --check
```

Artifacts: `build/T4_USB_ACM_01/{zImage,handoff.bin,initramfs.cpio.gz,vmlinux,
manifest.json,usb-acm01-only.patch}`. These Linux payloads are uploaded by the
existing checked RAM loader, not passed individually to a DFU native-image
loader. The CPIO is minimal; PID1 creates only a RAM ttyGS0 character node from
its real sysfs major/minor, mounts proc/sysfs, and sends heartbeat/echo. No block
device is opened or mounted. There are no Android image/storage operations.
