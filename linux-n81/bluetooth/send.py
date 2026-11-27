#!/usr/bin/env python3
"""send.py IPOD_IP LOCAL REMOTE: copy a file to the running iPod over Wi-Fi (RAM only)."""
import hashlib, pathlib, socket, subprocess, sys, time
ip, local, remote = sys.argv[1:4]
shell = pathlib.Path(__file__).resolve().parents[1] / 'shell.py'
data = pathlib.Path(local).read_bytes()
subprocess.run([sys.executable, str(shell), '--timeout', '30', '-c',
                f'(nc -l -p 5199 > {remote} &) ; sleep 1'], check=True, stdout=subprocess.DEVNULL)
with socket.create_connection((ip, 5199), timeout=60) as s:
    s.sendall(data)
    s.shutdown(socket.SHUT_WR)
# the receiver keeps writing after the socket closes: wait for the full size
wait = f'i=0; while [ "$(stat -c %s {remote})" != {len(data)} ] && [ $i -lt 120 ]; do sleep 1; i=$((i+1)); done; md5sum {remote}'
out = subprocess.run([sys.executable, str(shell), '--timeout', '150', '-c', wait],
                     capture_output=True, text=True).stdout
ok = hashlib.md5(data).hexdigest() in out
print(f'{remote}: {len(data)} bytes {"ok" if ok else "CHECKSUM MISMATCH"}')
sys.exit(not ok)
