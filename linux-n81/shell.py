#!/usr/bin/env python3
"""Terminal for the Linux USB serial shell on the iPod (VID:PID 0525:a4a7).

  shell.py              interactive; Ctrl-] quits
  shell.py -c COMMAND   run one command and print its output
  shell.py --push FILE REMOTE   copy a file to the device RAM and verify it
"""
import argparse
import glob
import hashlib
import os
from pathlib import Path
import re
import select
import sys
import termios
import time
import tty


def find_port():
    for node in glob.glob('/sys/class/tty/ttyACM*'):
        usb = Path(node, 'device').resolve().parent
        try:
            ids = (usb / 'idVendor').read_text().strip(), (usb / 'idProduct').read_text().strip()
        except OSError:
            continue
        if ids == ('0525', 'a4a7'):
            return '/dev/' + Path(node).name
    sys.exit('iPod serial port (0525:a4a7) not found')


def wait_for(port, marker, timeout):
    data, deadline = b'', time.monotonic() + timeout
    while time.monotonic() < deadline:
        if select.select([port], [], [], 0.2)[0]:
            data += os.read(port, 4096)
            if marker in data and b'\n' in data[data.find(marker):]:
                return data[data.find(marker) + len(marker):]
    sys.exit('timeout; device said: ' + data[-300:].decode(errors='replace'))


def push(port, content, remote):
    # Bytes are sent only after READY, which is printed only if raw mode was
    # set: otherwise the shell would run the file contents as commands. The
    # applets are called through busybox because /bin may lack the links.
    bb = '/bin/busybox'
    os.write(port, f"\n{bb} stty raw -echo && echo __N81''_READY__ && "
                   f"{bb} head -c {len(content)} > {remote}; {bb} stty sane; "
                   f"echo __N81''_SUM__ $({bb} md5sum {remote})\n".encode())
    wait_for(port, b'__N81_READY__', 10)
    view = memoryview(content)
    while view:
        view = view[os.write(port, view[:4096]):]
    digest = wait_for(port, b'__N81_SUM__ ', 60).split()[0].decode()
    if digest != hashlib.md5(content).hexdigest():
        sys.exit(f'checksum mismatch after copy: {digest}')
    print(f'{remote}: {len(content)} bytes copied and verified')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-c', dest='command')
    parser.add_argument('--timeout', type=float, default=15)
    parser.add_argument('--push', nargs=2, metavar=('FILE', 'REMOTE'))
    args = parser.parse_args()
    if args.push and not re.fullmatch(r'[A-Za-z0-9_./-]+', args.push[1]):
        sys.exit('remote path may only contain letters, digits, _ . / -')
    port = os.open(find_port(), os.O_RDWR | os.O_NOCTTY)
    tty.setraw(port)  # without this the host echoes device output back to it
    termios.tcflush(port, termios.TCIOFLUSH)
    if args.push:
        return push(port, Path(args.push[0]).read_bytes(), args.push[1])
    if args.command:
        # The quotes keep the markers out of the echoed command line. The
        # leading newline discards anything left over on the input line.
        os.write(port, f"\necho __N81''_BEGIN__; {args.command}; echo __N81''_END__ $?\n".encode())
        data, deadline = b'', time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            if select.select([port], [], [], 0.2)[0]:
                data += os.read(port, 4096)
                text = data.replace(b'\r', b'')
                begin = text.find(b'__N81_BEGIN__\n')
                end = text.find(b'__N81_END__ ', begin + 1)
                if begin >= 0 and end >= 0 and b'\n' in text[end:]:
                    sys.stdout.buffer.write(text[begin + len(b'__N81_BEGIN__\n'):end])
                    return int(text[end:].split()[1])
        sys.stdout.buffer.write(data)
        sys.exit('\ntimeout waiting for the shell')
    saved = termios.tcgetattr(sys.stdin)
    print('connected; Ctrl-] quits', flush=True)
    try:
        tty.setraw(sys.stdin)
        os.write(port, b'\n')
        while True:
            ready = select.select([port, sys.stdin], [], [])[0]
            if port in ready:
                os.write(sys.stdout.fileno(), os.read(port, 4096))
            if sys.stdin in ready:
                key = os.read(sys.stdin.fileno(), 1024)
                if b'\x1d' in key:
                    return 0
                os.write(port, key)
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, saved)


if __name__ == '__main__':
    sys.exit(main())
