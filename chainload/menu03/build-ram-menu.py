#!/usr/bin/env python3
"""Create a RAM-only test entry without changing the production menu image."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
OUT=ROOT/'saved/build/untethered-menu-03';CROSS=str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-')
def main():
    subprocess.run([CROSS+'gcc','-nostdlib','-fno-use-linker-plugin','-mcpu=cortex-a8','-marm',
       '-Wl,-Ttext=0x44000300','-Wl,-e,_start','-Wl,--build-id=none',str(HERE/'oib-entry.S'),'-o',str(OUT/'oib-entry.elf')],check=True)
    subprocess.run([CROSS+'objcopy','-O','binary',str(OUT/'oib-entry.elf'),str(OUT/'oib-entry.bin')],check=True)
    prefix=(OUT/'oib-entry.bin').read_bytes();assert len(prefix)<0x100
    production=(OUT/'menu-post-loader.bin').read_bytes();ram=bytearray(production)
    assert not any(production[0x300:0x400]);ram[0x300:0x300+len(prefix)]=prefix
    assert ram[0x1000:]==(OUT/'openiboot-native.bin').read_bytes()
    (OUT/'menu-full-ram-test.bin').write_bytes(ram)
    (OUT/'MENU-RAM-BUILD.json').write_text(json.dumps(dict(entry='0x44000300',
      production_sha256=hashlib.sha256(production).hexdigest(),ram_test_sha256=hashlib.sha256(ram).hexdigest(),
      native_payload_unchanged=True,prefix_bytes=len(prefix),hardware_test=False),indent=2)+'\n')
    print('RAM-only full menu test image:',OUT/'menu-full-ram-test.bin')
if __name__=='__main__':main()
