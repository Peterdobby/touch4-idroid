#!/usr/bin/env python3
"""Inspect an Apple .mtprops plist; explicitly extract one Constructed Firmware blob.
Host files only. Does not establish N81/panel compatibility or operate any device.
"""
import argparse,hashlib,json,plistlib
from pathlib import Path

def candidates(obj,path=''):
    out=[]
    if isinstance(obj,dict):
        data=obj.get('Constructed Firmware')
        if isinstance(data,bytes):
            out.append((path or '/',data,{'fields':sorted(map(str,obj)),'other_data':{str(k):{'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for k,v in obj.items() if isinstance(v,bytes) and k!='Constructed Firmware'}}))
        for k,v in obj.items():
            if isinstance(v,(dict,list)):out+=candidates(v,path+'/'+str(k).replace('~','~0').replace('/','~1'))
    elif isinstance(obj,list):
        for i,v in enumerate(obj):out+=candidates(v,path+'/'+str(i))
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('plist',type=Path)
    p.add_argument('--entry',help='exact path shown in candidate list; never auto-select a legacy model')
    p.add_argument('--out-dir',type=Path,help='new host directory, required with --entry')
    a=p.parse_args()
    if bool(a.entry)!=bool(a.out_dir):p.error('--entry and --out-dir must be supplied together')
    data=a.plist.read_bytes()
    if len(data)>32*1024*1024:p.error('plist exceeds 32 MiB inspection limit')
    items=candidates(plistlib.loads(data))
    report={'source':str(a.plist.resolve()),'source_sha256':hashlib.sha256(data).hexdigest(),'board_panel_compatibility':'UNVERIFIED: extraction alone does not establish N81 compatibility','candidates':[{'entry':path,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),**meta} for path,blob,meta in items]}
    if a.entry:
        found=[(path,b,m) for path,b,m in items if path==a.entry]
        if len(found)!=1:p.error('entry not uniquely found; inspect candidate list first')
        path,blob,meta=found[0]
        if not 32<=len(blob)<=8*1024*1024:p.error('firmware length outside 32 bytes..8 MiB')
        a.out_dir.mkdir(parents=True,exist_ok=False)
        (a.out_dir/'zephyr2.bin').write_bytes(blob)
        report['selected']=path
        (a.out_dir/'extraction.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
