# Third-party components and licensing

Original copyright notices are retained. Project integration code is released under the root GPL-3.0-or-later license; Linux-derived content and third-party sources retain their own license terms.

| Component | Source / baseline | License scope |
| --- | --- | --- |
| OpeniBoot | [iDroid-Project/openiBoot](https://github.com/iDroid-Project/openiBoot), `c5cee8c` | GPL-3.0-or-later |
| iDroid Linux | [iDroid-Project/iDroid-kernel](https://github.com/iDroid-Project/iDroid-kernel), `idroid-3.0.0` | Linux GPL-2.0; kernel-derived changes retain this license |
| Legacy iOS Kit | [LukeZGD/Legacy-iOS-Kit](https://github.com/LukeZGD/Legacy-iOS-Kit) | External dependency; its complete tool collection is not bundled |
| libirecovery source | `tools/libirecovery-1.3.1.c`, original copyright header retained | LGPL-2.1, as stated in the file |
| libusb and ARM toolchain | External build dependencies | Compiled binaries are not bundled; upstream licenses apply |
| androidi4 / Android userspace | Existing local experimental package | Not distributed here; no license is asserted over the complete package |
| Apple firmware, iBoot, DeviceTree, tickets, and N1 firmware | Owner-supplied inputs | Excluded from this repository; not covered by the root license |

`LICENSES/` contains the relevant GNU license texts. Kernel-derived sources and generated kernel changes in `linux-ramtest/`, together with `patches/kernel-ramtest.patch`, retain the Linux GPL-2.0 license scope. This release does not relicense proprietary firmware or remove third-party copyright notices.
