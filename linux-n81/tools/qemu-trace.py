import json, os, shutil, socket, struct, subprocess, time, wave, sys
os.chdir('/lab')
shutil.rmtree('ov', ignore_errors=True); os.mkdir('ov'); shutil.copy('dev/nor.bin', 'ov/nor.bin')
for f in ('q.sock', 'trace.fifo', 'out.wav'):
    if os.path.exists(f): os.remove(f)
os.mkfifo('trace.fifo')
keep = r"cs42l58_log|addr 0x(bf100[01]|bfa00|845)[0-9a-f]* "
grep = subprocess.Popen(f"grep -E '{keep}' < trace.fifo > trace.txt", shell=True)
fw = 'app/usr/lib/lighttouch/firmwarekit'
args = [fw, 'oneshot', 'LightTouchMac', '-M',
        'iPod-Touch-4G,kboot=dev/kboot.bin,nand=dev/nand,nand-overlay=ov,nor-rw=ov/nor.bin,wifi=off',
        '-accel', 'tcg', '-display', 'none', '-monitor', 'none', '-no-reboot',
        '-audio', 'driver=wav,path=/lab/out.wav', '-serial', 'file:serial.log',
        '-qmp', 'unix:/lab/q.sock,server,nowait',
        '-trace', 'cs42l58_log', '-trace', 'memory_region_ops_write', '-D', '/lab/trace.fifo']
q = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=open('engine.log', 'w'), stderr=subprocess.STDOUT)
for _ in range(600):
    if os.path.exists('q.sock') or q.poll() is not None: break
    time.sleep(0.1)
s = socket.socket(socket.AF_UNIX); s.connect('q.sock'); r = s.makefile('r')
def cmd(c, **a):
    s.sendall((json.dumps({'execute': c, 'arguments': a}) + '\n').encode())
    while True:
        m = json.loads(r.readline())
        if 'return' in m or 'error' in m: return m
r.readline(); cmd('qmp_capabilities')
t0 = time.time()
def note(msg):
    n = sum(1 for _ in open('trace.txt', errors='replace'))
    print(f'{time.time()-t0:6.1f}s {msg}: {n} trace lines', flush=True)
def press(name, hold=0.2):
    x = cmd('qom-set', path='/machine', property=name, value=True)
    time.sleep(hold); cmd('qom-set', path='/machine', property=name, value=False)
    note(f'{name} {x.get("error", {}).get("desc", "")}')
for i in range(8): time.sleep(10); note('boot')
for name in ('button-home', 'button-hold', 'button-home', 'button-hold'):
    press(name); time.sleep(8); note('after')
try: cmd('screendump', filename='/lab/screen.ppm')
except Exception as e: print(e)
cmd('quit'); q.wait(timeout=60); grep.wait(timeout=60)
note(f'end rc={q.returncode}')
