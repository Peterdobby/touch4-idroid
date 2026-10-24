# Building and private inputs

This is a source release of the verified working tree. Complete local binaries remain in `saved/releases/`. Offline checks can run after cloning; rebuilding the full firmware requires the original inputs, toolchain, and protected baselines.

## Dependencies

- Python 3.9+, Bash, Clang, and an existing Legacy iOS Kit installation.
- A GNU ARM EABI toolchain for ARM components.
- macOS Clang, `ld-classic`, and local linker stubs for Mach-O helpers.
- OpeniBoot `c5cee8c`, the captured controlled iBoot environment, Android TOUCH03, and checksum manifests for the complete menu build.
- Owner-supplied Apple inputs, signing tickets, N1 firmware, and device calibration. These are excluded from the public repository.

## Layout

Build outputs, upstream inputs, toolchains, and logs belong under `saved/`. Historical scripts retain some dependency conventions from the original working tree and must be used with their input manifests. A clean clone alone does not rebuild the complete firmware from scratch.

The original local working tree keeps compatibility symlinks such as `build/` and `releases/`, while their actual contents reside under `saved/`. Successful snapshots retain their original manifest hashes; they have not been rewritten in bulk.

## Main components

| Directory | Purpose |
| --- | --- |
| `installer/t4-android02/` | Installer 02.4, component downloads, complete image sets, and tests |
| `chainload/menu04/` | Target iBoot menu and RAM file loading |
| `chainload/menu03/` | Previously verified iOS 7.1.2 / Android menu baseline |
| `chainload/untethered-oib02/` | Apple update API ordering, preflight checks, and complete-set tests |
| `linux-ramtest/android-touch03/` | Current Android RAM build without the diagnostic overlay |
| `linux-ramtest/android-touch02/` | Real N1 touch input, active-low readiness, and the Home/touch fix |
| `phase1/` | Existing RAM boot workflow using external Kit components |
| `tools/native_image.py` | Native packaging that preserves every raw payload byte |

## Offline checks

```bash
python3 installer/t4-android02/tests.py
python3 installer/t4-android02/test_profiles.py
python3 tools/test_native_image.py
bash -n start.sh installer/t4-android02/start.sh
```

These checks do not operate the device. Native image validation and raw-image rejection run independently. Two binary-rebuilding integration checks require the GNU ARM toolchain and local reference images; they are explicitly skipped when those inputs are missing. Set `CROSS` to the toolchain prefix and `T4_REFERENCE_BUILD_DIR` to the reference image directory.

Builders generally refuse to overwrite protected outputs. Use a new output directory for new experiments.

## Native packaging

With the matching baseline and toolchain available:

```bash
python3 tools/make-openiboot-native.py \
  saved/build/openiboot.bin \
  saved/build/openiboot-native-generated.bin
```

The payload starts at offset `0x1000` and is preserved byte for byte. This wrapper implements the existing 4.1 iBSS contract; it is not a universal entry point for arbitrary iBoot versions.

The public copy removes original machine paths, the owner's ECID, and default passwords. Device configuration comes from local environment settings or private inputs. These publication changes do not establish compatibility with other devices or iOS releases.
