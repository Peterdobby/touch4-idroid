"""Build a minimal ARMv7 initramfs with no Android dependencies."""

import argparse
import gzip
from pathlib import Path
import subprocess
import tempfile


def entry(name, inode, mode, data=b"", rdev_major=0, rdev_minor=0):
    path = name.encode("ascii") + b"\0"
    fields = (inode, mode, 0, 0, 1, 0, len(data), 0, 0,
              rdev_major, rdev_minor, len(path), 0)
    header = b"070701" + "".join(f"{value:08x}" for value in fields).encode()
    record = header + path
    return record + b"\0" * (-len(record) % 4) + data + b"\0" * (-len(data) % 4)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New initramfs.cpio.gz file")
    parser.add_argument("--linker", default="ld.lld", help="LLVM linker path or name")
    args = parser.parse_args()
    source = Path(__file__).with_name("init.S")
    with tempfile.TemporaryDirectory() as temp:
        init = Path(temp) / "init"
        subprocess.run([
            "clang", "--target=armv7a-linux-gnueabi", f"--ld-path={args.linker}", "-nostdlib",
            "-static", "-Wl,--build-id=none", str(source), "-o", str(init),
        ], check=True)
        archive = b"".join((
            entry("dev", 1, 0o40755),
            entry("dev/console", 2, 0o20600, rdev_major=5, rdev_minor=1),
            entry("init", 3, 0o100755, init.read_bytes()),
            entry("TRAILER!!!", 0, 0),
        ))
    with args.output.open("xb") as output:
        output.write(gzip.compress(archive, mtime=0))


if __name__ == "__main__":
    main()
