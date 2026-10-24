#!/usr/bin/env python3
"""Read N81 touch IORegistry through USB diagnostics or existing SSH + Python.
USB diagnostics needs no iOS Python. SSH sends code via stdin with -B.
No helper upload/install and no device file writes.
Saves XML properties/calibration on the Mac only. Does not boot or restore iOS.
"""
import argparse,base64,datetime,hashlib,json,plistlib,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__)
 mode=p.add_mutually_exclusive_group(required=True)
 mode.add_argument('--target',help='existing SSH destination, e.g. root@127.0.0.1')
 mode.add_argument('--diagnostics',action='store_true',help='Read via host libimobiledevice; no SSH or iOS Python required')
 p.add_argument('--udid',help='Specific USB iOS device for --diagnostics; otherwise require exactly one')
 p.add_argument('--port',type=int,default=2222)
 p.add_argument('--legacy-rsa',action='store_true',help='Allow ssh-rsa host keys for this SSH connection only; keep host verification enabled')
 a=p.parse_args()
 if a.target and (not re.fullmatch(r'[A-Za-z0-9_.@:-]+',a.target) or a.target.startswith('-') or not 1<=a.port<=65535):p.error('Invalid SSH destination/port')
 remote="export PYTHONDONTWRITEBYTECODE=1; if command -v python2 >/dev/null 2>&1; then exec python2 -B -; elif command -v python >/dev/null 2>&1; then exec python -B -; elif command -v python3 >/dev/null 2>&1; then exec python3 -B -; else echo 'No existing iOS Python. Stop; no installation or upload performed.' >&2; exit 2; fi"
 if a.diagnostics:
  def hosttool(name):
   found=shutil.which(name)
   if found:return found
   for directory in ['/opt/local/bin','/opt/homebrew/bin','/usr/local/bin']:
    candidate=Path(directory)/name
    if candidate.is_file():return str(candidate)
   raise RuntimeError('Missing existing host tool: '+name)
  def run(args):
   result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
   if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace') or result.stdout.decode(errors='replace'))
   return result.stdout
  udid=a.udid
  if not udid:
   devices=run([hosttool('idevice_id'),'-l']).decode().split()
   if len(devices)!=1:raise RuntimeError('Require exactly one USB iOS device or select --udid')
   udid=devices[0]
  machine=run([hosttool('ideviceinfo'),'-u',udid,'-k','ProductType']).decode().strip()
  if machine!='iPod4,1':raise RuntimeError('N81 identity not confirmed: '+machine)
  data={'machine':machine,'method':'read-only USB diagnostics IORegistry','entries':{}}
  for name in ['AppleMultitouchN1SPI','multi-touch','spi1']:
   xml=run([hosttool('idevicediagnostics'),'-u',udid,'ioregentry',name])
   obj=plistlib.loads(xml)
   entry=obj.get('IORegistry')
   if not isinstance(entry,dict) or not entry:continue
   data['entries'][name]=base64.b64encode(plistlib.dumps(entry)).decode()
  if not data['entries']:raise RuntimeError('No touch IORegistry entries returned')
  raw_json=json.dumps(data,indent=2).encode()+b'\n'
 else:
  code=(ROOT/'saved/research/touch-bringup/read-ios-touch.py').read_bytes()
  ssh=['ssh','-T','-o','ConnectTimeout=10']
  if a.legacy_rsa:ssh+=['-o','HostKeyAlgorithms=+ssh-rsa']
  r=subprocess.run(ssh+['-p',str(a.port),a.target,remote],input=code,stdout=subprocess.PIPE)
  if r.returncode:return r.returncode
  raw_json=r.stdout;data=json.loads(raw_json)
 if data.get('machine')!='iPod4,1':raise RuntimeError('N81 identity not confirmed')
 out=ROOT/'saved/research/touch-bringup'/('ios-live-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));out.mkdir(exist_ok=False)
 (out/'io-registry.json').write_bytes(raw_json)
 manifest={'machine':data['machine'],'method':data.get('method','SSH read-only IORegistry'),'calibration':[],'runtime_parameters':{}}
 keys=['fw-execute-addr','cal-dl-addr','fll-mval','fll-mval-addr','const-cal-addr','const-cal-val','clk32-clock-enable-addr','clk32-clock-enable-val','ref-clk-div-addr','ref-clk-div-val','reset-deassert-high-z','reset-deassert-delay']
 for name,encoded in data['entries'].items():
  if encoded is None:continue
  xml=base64.b64decode(encoded);(out/(name+'.plist')).write_bytes(xml);obj=plistlib.loads(xml)
  manifest['runtime_parameters'][name]={k:obj[k] for k in keys if k in obj and isinstance(obj[k],(int,str,bool))}
  for key in ['multi-touch-calibration','Calibration Data']:
   blob=obj.get(key)
   if isinstance(blob,bytes) and 16<=len(blob)<=4096 and any(blob):
    path=out/(name+'-MtCl.bin');path.write_bytes(blob)
    manifest['calibration'].append({'path':str(path),'property':key,'size':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'NI_prefix':blob[:2]==b'NI'})
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2));print('Host output:',out)
 if not manifest['calibration']:print('No nonzero calibration found; preserve the runtime properties for analysis.');return 2
 return 0
if __name__=='__main__':
 try:raise SystemExit(main())
 except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired,plistlib.InvalidFileException) as e:print(e,file=sys.stderr);raise SystemExit(1)
