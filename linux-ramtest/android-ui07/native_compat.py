"""Hash-guarded, minimal native fallback for the exact original androidi4 DSO.
Equivalent C-source diff is supplied separately. No binary layout, ABI,
relocation, prelink address, native update implementation or other JNI changes.
"""
import hashlib,struct
ORIGINAL='23b0ceb7b32d3fc737fd944492a08762cb81fd0e4d83b034bb2ccd5a85e3cd2a'
def patch_battery(data):
    assert hashlib.sha256(data).hexdigest()==ORIGINAL,'unexpected original libandroid_servers.so'
    out=bytearray(data)
    assert struct.unpack_from('<H',out,0x6bf0)[0]==0x1c23 # mov r3,r4 (printf path argument)
    assert struct.unpack_from('<H',out,0x6bfc)[0]==0xe22a # b 0x7054 (return -1)
    # Null-directory path still has JNIEnv in r5. Jump directly to original
    # FindClass/field/native registration; skip only path-discovery diagnostics.
    assert struct.unpack_from('<H',out,0x6bf6)[0]==0x2006
    struct.pack_into('<H',out,0x6bf6,0x2005) # recovered absence is WARN, not ERROR
    struct.pack_into('<H',out,0x6bfc,0xe000|((0x7032-0x6bfc-4)//2)) # b original FindClass/field/native registration
    old=b'Could not open %s\n\0';new=b'Battery: UNKNOWN\n\0'
    assert data.count(old)==1 and len(new)<=len(old)
    off=data.index(old);out[off:off+len(old)]=new+bytes(len(old)-len(new))
    assert len(out)==len(data) and out[-8:]==data[-8:]
    allowed=set(range(0x6bfc,0x6bfe))|set(range(0x6bf6,0x6bf8))|set(range(off,off+len(old)))
    assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(data,out)))
    return bytes(out),{'original_sha256':ORIGINAL,'patched_sha256':hashlib.sha256(out).hexdigest(),'instruction_changes':{'0x6bf6':'log recovered missing hardware as WARN','0x6bfc':'continue at original field/native registration 0x7032'},'log_string_offset':hex(off),'layout_and_prelink_preserved':True,'without_power_supply':'native_update registered; original update returns battery UNKNOWN/present=false','hardware_readings':'not simulated','kernel_modified':False}

RUNTIME_ORIGINAL='9e5766a03f828ffa2163dc7721249276aad10373ddb16f15c40bac1344e1b4d1'
def patch_zygote_ids(data,here,out,cross):
    import subprocess
    assert hashlib.sha256(data).hexdigest()==RUNTIME_ORIGINAL,'unexpected libandroid_runtime.so'
    assert data[0x5d7c4:0x5d7ca].hex()=='70b5141c1d1c'
    assert data[0x5d7e4:0x5d7ea].hex()=='70b5141c1d1c'
    subprocess.run([cross+'as','-mcpu=cortex-a8',str(here/'zygote-id-fix.S'),'-o',str(out/'zygote-id-fix.o')],check=True)
    subprocess.run([cross+'ld','-Ttext=0x5d7c4','-e','t4_setregid_fix','--build-id=none','--defsym','errno_plt=0x20178','--defsym','setregid_plt=0x230ac','--defsym','setreuid_plt=0x230b8',str(out/'zygote-id-fix.o'),'-o',str(out/'zygote-id-fix.elf')],check=True)
    subprocess.run([cross+'objcopy','-O','binary','-j','.text',str(out/'zygote-id-fix.elf'),str(out/'zygote-id-fix.bin')],check=True)
    code=(out/'zygote-id-fix.bin').read_bytes();assert len(code)==64
    patched=bytearray(data);patched[0x5d7c4:0x5d804]=code
    assert len(patched)==len(data) and patched[-8:]==data[-8:]
    assert patched[:0x5d7c4]==data[:0x5d7c4] and patched[0x5d804:]==data[0x5d804:]
    return bytes(patched),{'original_sha256':RUNTIME_ORIGINAL,'patched_sha256':hashlib.sha256(patched).hexdigest(),'ranges':[[0x5d7c4,0x5d7e4],[0x5d7e4,0x5d804]],'semantics':'return 0 on successful setregid/setreuid; return real errno on failure','layout_prelink_JNI_tables_unchanged':True}
