#!/usr/bin/env python3
from pathlib import Path
import gzip,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/T4_ANDROID_INPUT_03';PREV=ROOT/'saved/build/T4_ANDROID_INPUT_02'
sys.path.insert(0,str(ROOT));from prepare_android import unpack_cpio
for n in ['zImage','zImage.original','Image.expected','Image.instrumented','vmlinux','kernel.config','android-init','libandroid_servers.so','libandroid_runtime.so','t4-ramclock','ram-clock-epoch']:
 assert (OUT/n).read_bytes()==(PREV/n).read_bytes(),n
oldrs,old=unpack_cpio(gzip.decompress((PREV/'initramfs.cpio.gz').read_bytes()));newrs,new=unpack_cpio(gzip.decompress((OUT/'initramfs.cpio.gz').read_bytes()))
assert set(new)-set(old)=={'sbin/t4-watch-bounded.sh'}
assert all(new[n]==d for n,d in old.items() if n!='sbin/t4-ui-watch.sh')
oldmeta={e['path']:e for e in oldrs};newmeta={e['path']:e for e in newrs}
for n in old:
 for key in ['mode','uid','gid','mtime','rdev_major','rdev_minor']:assert oldmeta[n][key]==newmeta[n][key],(n,key)
watch=new['sbin/t4-ui-watch.sh'].decode()
assert 'android.settings.SETTINGS' not in watch and 'input keyevent' not in watch
for line in watch.splitlines():
 tokens=line.split()
 if not tokens or tokens[0].startswith('#'):continue
 if '/system/bin/' in line:assert tokens[0]=='run_bounded',line
assert 'run_bounded 10' in watch and 'svc power stayon true' in watch and 'phase=8' in watch and 'phase=9' in watch
assert b'IN02 P=' in (OUT/'Image.expected').read_bytes()
m=json.loads((OUT/'manifest.json').read_text());assert m['pinned_kernel_variant']=='T4_ANDROID_INPUT_02'
for p,d in m['protected_baselines'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==d,p
result={'INPUT02_native_kernel_byte_identical':True,'Android_libraries_APK_ODEX_nodes_keylayout_preserved':True,'CPIO_delta':['replace sbin/t4-ui-watch.sh','add sbin/t4-watch-bounded.sh'],'commands_bounded_and_no_Settings_or_sync_key_injection':True,'previous_baselines_unchanged':True,'hardware':'pending'}
(OUT/'userspace-test.json').write_text(json.dumps(result,indent=2)+'\n');print('INPUT03_BUNDLE_PASSED: exact INPUT02 native kernel; only watch+guard changes; previous artifacts preserved')
