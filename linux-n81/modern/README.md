# Linux 6.17 for N81AP

Kernel: `archeYR/linux`, branch `apple-n90`, commit `8e79d535`, the same tree
as [kpoxo6op/iphone4-linux](https://github.com/kpoxo6op/iphone4-linux) for the
iPhone 4 (same S5L8930 SoC). `s5l8930-apple-n81.dts` is derived from the N90
device tree; `config.sh` lists the options set on top of `s5l8930_defconfig`;
`patches/` is applied once by `build.sh`.

`build.sh` runs two passes: the kernel and modules, then the user programs
(`n81-bt`, `n81-wifi`, `n81-buttons`, the ALSA driver), the root file system
from `../gui/build.py` and the final `zImage` with it built in.
`../work/zImage-n81` is the zImage with the DTB appended.

`package.py` checks the size limits and builds the handoff stub and USB loader
from `../../linux-ramtest` into `../work/pkg`.
