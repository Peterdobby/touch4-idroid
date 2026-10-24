# OpeniBoot c5cee8c ↔ Linux A4 USB comparison

**Measurements are not source constants.** Only the four OIB HWCFG values below
are available from a successful physical run. Linux USB01 faulted before clock/
PHY init and did not print the other requested register states. Its GOTGINT
0bad0add is observed; treating that as a normal OTG status is unsafe. ACM01
adds real snapshots. The measured ACM01 runtime values are now recorded below.
The large source comparison table retains intended values and is not a runtime
dump. Unit-test GSNPSID4f54280a is a fixture, not the measured T4 core ID.

| Item / physical register | Successful OIB evidence | USB01 physical evidence | ACM01 intended sequence / diagnostics |
|---|---|---|---|
| Controller / IRQ | Source86100000, IRQ0d; working ACM | Registered existing resource; stage1 then ISR | Same resource/IRQ; IRQ requested only after state ready |
| PHY | Source86000000 | PHY init not reached | Static mapping fcc00000 →86000000; Linux A4 cpu.c mapping |
| OTG clock gate BF101070 | Source gate18 RMW enable; value unrecorded | enable not reached; raw value unrecorded | Existing clock API enables child18; print actual value |
| PHY clock gate BF101084 | Source gate1d RMW enable; value unrecorded | enable not reached | Existing parent usbreg1d; print actual value |
| PHY+00 OPHYPWR | Source writes00000006 | Not measured | Write6, log readback |
| PHY+60 /+1c /+44 | Source writes200 /6 /733 | Not measured | Same order and values; 10us after final power write |
| PHY+04 OPHYCLK | Source RMW low2:12MHz0,24MHz1,48MHz2 | Not measured | Same encoding; read clk_xusbxti, reject unknown before writes |
| PHY+08 ORSTCON | Source setbit0;20us; clearbit0;1000us | Not measured | Same order/delays, preserve other bits |
| Controller+e00 PCGCCTL | Source clears low2;100us | Not measured | Same, before PHY init |
| +804 DCTL | Source disconnect bit1;4000us, later reconnect;250us | Not measured | Same PHY preamble; hold disconnected until EP0 ready |
| +40 GSNPSID | Not logged in successful OIB log | Not measured | Log actual ID; reject0/ffffffff/0bad0add |
| +44 GHWCFG1 | **00000264** | Not measured | Print actual; expected to compare with OIB |
| +48 GHWCFG2 | **228f60d0** | Not measured | Print actual; 8 non-control endpoints in recorded OIB value |
| +4c GHWCFG3 | **07e800e8** (2024 FIFO words) | Not measured | Print actual; reject depth<1664 before FIFO layout writes |
| +50 GHWCFG4 | **dbf08030** (dedicated FIFO support) | Not measured | Existing Linux core selects dedicated FIFOs from readback |
| +10 GRSTCTL | Source CSftRst=1 → waitclear → waitAHBIdle;1000us | Not measured | Existing bounded Linux waits; callback1000us settle |
| +0c GUSBCFG | Source intended00001708, not readback | Not measured | Existing Linux intended0000140f (16bit, turn5,TOutCal7); no HNP/SRP advertised |
| +08 GAHBCFG | Source intended0000002b (DMA/incr8/global IRQ) | Not measured | PIO:0 during probe;1 only after EP0 ready. OIB DMA settings intentionally not copied |
| +04 GOTGINT | No measured snapshot | **0bad0add** in IRQ before clock/PHY | W1C before registering IRQ; not interpreted as an ID or PHY failure |
| +14 GINTSTS | No measured snapshot | No separate snapshot | W1C pending status before IRQ claim; read actual first8 IRQs |
| +18 GINTMSK | Source0 during setup;3000 reset/enum initial mask | No separate snapshot | 0 through probe; existing Linux gadget mask after bind |
| +810/+814/+81c endpoint IRQ masks | Source0 during setup | Endpoint software state uninitialized | Platform pre-mask0; Linux core later programs masks after state valid |
| +00 GOTGCTL | Source reconnect then OR bit1 SessionRequest | No snapshot | A4 pullup does same delay250us/OR2; prints actual session-valid bits, no fabricated VBUS |

Successful measured HWCFG source:
`logs/phase1-published-20261019-211342.log` (USB Hardware Configuration block).
Linux failing transfer log:
`logs/linux-ram-20261019-220853.log` only covers OpeniBoot/handoff; the actual
Linux fault evidence is `<HOME>/Desktop/IMG_8238.jpeg`.

## ACM01 physical runtime measurements — 2026-10-20

| Field | Measured |
|---|---|
| Host identity | 0525:a4a7; Gadget Serial v2.4; Linux 3.0.8 with s3c-hsotg |
| Host serial port | /dev/cu.usbmodem14701 opened successfully |
| GSNPSID | **4f54272a** |
| GINTSTS / GINTMSK | **04008028 / f00c3cd4**; AND=0 |
| GOTGCTL / DCTL | **000d0002 / 00000000** |
| UDC stage | **20**, gadget bound |
| IRQ / SET | **39→43 /13→14**, then stable in supplied status lines |
| Data | RAM heartbeat received and host T4_HOST_ECHO_CHECK returned |

This confirms enumeration, serial open and bidirectional USB data. Android ADB
remains untested. The pasted excerpt has no final script-summary/exit line;
confirmation uses actual received data plus independent read-only host USB
inventory. Clock/PHY/reset readbacks remain absent from this excerpt. Tested
binaries and original manifest were hash-verified and left unchanged.
Evidence: `build/T4_USB_ACM_01/HARDWARE-RESULT.json`.

## Reference order, including deliberate Linux ownership differences

OpeniBoot usb_setup:
wait10ms → gate18 on → gate1d on → PCGCCTL low2clear →100us → DCTL disconnect
→4000us → PHY+60=200,+00=6,+1c=6,+44=733 →10us → clockselect → resetbit0 set
→20us → resetbit0 clear →1000us → readHWCFG → installhandler → usb_start.

usb_start:
CSftRst → waitclear → waitAHBIdle →1000us → FIFO capability selection →
DMA/GUSBCFG/DCFG → mask general/endpoint interrupts and acknowledge pending
endpoint bits → reconnect →250us → SessionRequest → reset/enum mask → enable
CPU IRQ. Controller endpoint/FIFO logic remains implemented by OIB there.

Linux retains its clock framework (parent1d then child18), controller reset,
PIO FIFO handling and gadget core. Apple PHY/link order is isolated in glue.
The Linux IRQ is not claimed until all request/endpoint state exists and
controller interrupts are masked. Linux generic core does not receive OIB's DMA
configuration, endpoint structures, transfer queues or USB protocol code.

The A4 branch of this OIB path has **no GPIO or PMU USB power operation**;
`power_ctrl(POWER_USB,ON)` and EDRAM gating are inside the USB_PHY_1G branch,
which A4 does not select. No such write is invented in Linux. OIB's reset polls
are unbounded; Linux retains bounded10k core/AHB and1k FIFO polls. A timeout is
reported as failure rather than extended indefinitely.

## Next measured comparison

Capture USB_LNX_01/02/03, USB_LNX_ID, USB_LNX_04_CORE_RESET,
USB_LNX_06_PROBE_OK, USB_LNX_07_EP0_READY and08_CONNECTED. Those report all
requested clock/PHY/GSNPSID/GRSTCTL/GUSBCFG/GAHBCFG/GINTSTS/GINTMSK fields.
This table deliberately leaves unavailable OIB/live Linux values unfilled.
