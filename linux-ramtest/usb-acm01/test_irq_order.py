#!/usr/bin/env python3
"""Run both actual probes; inject a synchronous IRQ inside request_irq.
Only OS allocation/clock/logging services and hardware register responses are
modeled. The probe, PHY glue, core/FIFO init, ISR and enqueue_setup execute ARM.
"""
from pathlib import Path
import json,shlex,struct,subprocess
from unicorn import *
from unicorn.arm_const import *
R=Path(__file__).resolve().parents[2];OUT=R/'saved/build/T4_USB_ACM_01';CROSS=str(R/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-')
REGS=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_R12,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_CPSR]
def execute(variant,fail=None):
    src=R/'sources'/('iDroid-kernel-'+variant);out=R/'build'/variant
    fields=['offsetof(struct s3c_hsotg,regs)','offsetof(struct s3c_hsotg,ctrl_req)','offsetof(struct s3c_hsotg,eps)','sizeof(struct s3c_hsotg_ep)','offsetof(struct s3c_hsotg_ep,queue)','offsetof(struct s3c_hsotg_ep,parent)','offsetof(struct s3c_hsotg_req,queue)']
    prefix=OUT/('offsets-'+variant)
    prefix.with_suffix('.c').write_text('#include "'+str(src/'drivers/usb/gadget/s3c-hsotg.c')+'"\nconst unsigned offsets[]={'+','.join(fields)+'};\n')
    cmd=shlex.split((src/'drivers/usb/gadget/.s3c-hsotg.o.cmd').read_text().splitlines()[0].split(' := ',1)[1]);cmd=cmd[:cmd.index('-c')];cmd=[x for x in cmd if not x.startswith(('-Wp,','-DKBUILD'))]
    subprocess.run(cmd+['-DKBUILD_MODNAME="test"','-c',str(prefix.with_suffix('.c')),'-o',str(prefix.with_suffix('.o'))],cwd=src,check=True,stdout=subprocess.DEVNULL)
    sy={p[2]:int(p[0],16) for l in subprocess.check_output([CROSS+'nm',str(out/'vmlinux')],text=True).splitlines() if len(p:=l.split())==3}
    nm=subprocess.check_output([CROSS+'nm',str(prefix.with_suffix('.o'))],text=True);offset=int(next(l.split()[0] for l in nm.splitlines() if l.split()[-1]=='offsets'),16)
    subprocess.run([CROSS+'objcopy','-O','binary','-j','.rodata',str(prefix.with_suffix('.o')),str(prefix.with_suffix('.bin'))],check=True)
    off,ctrl,eps,stride,queue,parent,reqqueue=struct.unpack_from('<7I',prefix.with_suffix('.bin').read_bytes(),offset)
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A8)
    BASE=0xc5000000;REQ=BASE+0x4000;PDEV=BASE+0x8000;RES=BASE+0x9000;CTRL=0xe0000000;STOP=0x1000000;IRQ_RETURN=STOP+4
    for a,n in [(0xc0000000,0x1000000),(BASE,0x10000),(CTRL,0x10000),(0xfcc00000,0x1000),(0xfc500000,0x10000),(STOP,0x1000)]:u.mem_map(a,n)
    u.mem_write(0xc0008000,(out/'Image.expected').read_bytes())
    def put(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
    def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    # Slab caches are initialized before probe in the real kernel.
    for i in range(0,64*4,4):put(sy['kmalloc_caches']+i,BASE+0xf000)
    put(RES,0x86100000);put(RES+4,0x8610ffff);put(PDEV+0x10,BASE+0x9800);u.mem_write(BASE+0x9800,b's3c-hsotg\0')
    if 'a4_hsotg_data' in sy and fail!='platform':put(PDEV+0x50,sy['a4_hsotg_data'])
    state={'clock':False,'allocs':0,'irq':0,'stages':[],'fault':None,'trace':[],'saved':None,'mmio_before_clock':0,'request_ready':None,'phy':False}
    modeled={0x40:0x4f54280a,0x44:0x264,0x48:0x228f60d0,0x4c:0x07e800e8,0x50:0xdbf08030}
    # ID is a model fixture, NOT an observed T4 GSNPSID.
    def ret(value=0):u.reg_write(UC_ARM_REG_R0,value&0xffffffff);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def hook(u,pc,size,data):
        if pc==IRQ_RETURN:
            for reg,val in zip(REGS,state['saved']):u.reg_write(reg,val)
            ret(-16 if fail=='irq' else 0);return
        names={v:k for k,v in sy.items()}
        name=names.get(pc,'')
        if name.startswith('s3c_hsotg_') and (not state['trace'] or state['trace'][-1]!=name):state['trace'].append(name)
        if pc==sy.get('kmem_cache_alloc'):
            state['allocs']+=1;ret(BASE if state['allocs']==1 else REQ);return
        if pc==sy.get('s3c_hsotg_ep_alloc_request') and fail=='alloc':ret(0);return
        if pc==sy.get('clk_get'):ret(BASE+0xa000);return
        if pc==sy.get('clk_get_rate'):ret(24000000);return
        if pc==sy.get('clk_enable'):state['clock']=fail!='clock';ret(-5 if fail=='clock' else 0);return
        if pc==sy.get('clk_disable'):state['clock']=False;ret();return
        if pc==sy.get('platform_get_resource'):ret(RES);return
        if pc==sy.get('__request_region'):ret(RES);return
        if pc==sy.get('__arm_ioremap'):ret(CTRL);return
        if pc==sy.get('platform_get_irq'):ret(13);return
        if pc==sy.get('t4_usb_stage'):state['stages'].append(u.reg_read(UC_ARM_REG_R0));ret();return
        if pc==sy.get('request_threaded_irq'):
            state['irq']+=1
            ctrlptr=get(BASE+ctrl)
            epready=all(get(BASE+eps+i*stride+parent)==BASE and get(BASE+eps+i*stride+queue)!=0 for i in range(9))
            state['request_ready']={'ctrl_req':bool(ctrlptr),'endpoints':epready,'clock':state['clock'],'GINTMSK':get(CTRL+0x18)}
            if variant=='T4_USB_ACM_01':assert ctrlptr and epready and state['clock'] and get(CTRL+0x18)==0,state
            if fail=='irq':ret(-16);return
            state['saved']=[u.reg_read(x) for x in REGS]
            u.reg_write(UC_ARM_REG_R0,13);u.reg_write(UC_ARM_REG_R1,BASE);u.reg_write(UC_ARM_REG_LR,IRQ_RETURN);u.reg_write(UC_ARM_REG_PC,sy['s3c_hsotg_irq']);return
        noop=['device_initialize','dev_set_name','dev_set_drvdata','clk_put','_dev_info','dev_err','dev_printk','dev_warn','printk','__const_udelay','__udelay','device_create_file','device_remove_file','kfree','__iounmap','release_resource','free_irq','t4_usb_irq_tick']
        if any(pc==sy.get(n) for n in noop):ret();return
        if pc==sy.get('snprintf'):u.mem_write(u.reg_read(UC_ARM_REG_R0),b'ep\0');ret(2);return
        if pc==sy.get('panic'):raise AssertionError('unexpected panic')
    def read(u,access,a,size,value,data):
        if CTRL<=a<CTRL+0x10000:
            if not state['clock']:
                state['mmio_before_clock']+=1;put(a,0x0bad0add)
            elif a in [CTRL+k for k in modeled]:put(a,0x0bad0add if fail=='id' and a==CTRL+0x40 else modeled[a-CTRL])
            elif a==CTRL+0x10:put(a,0x80000000)
            elif a==CTRL+0x14:put(a,0x2000) # pending EnumDone; mask must exclude before bind
    def invalid(u,access,a,size,value,data):
        state['fault']={'address':a,'PC':u.reg_read(UC_ARM_REG_PC),'LR':u.reg_read(UC_ARM_REG_LR),'r1':u.reg_read(UC_ARM_REG_R1),'registers':{str(r):u.reg_read(r) for r in REGS}};return False
    u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_MEM_READ,read);u.hook_add(UC_HOOK_MEM_INVALID,invalid)
    u.reg_write(UC_ARM_REG_CPSR,0xd3);u.reg_write(UC_ARM_REG_SP,0xc0fff000);u.reg_write(UC_ARM_REG_R0,PDEV);u.reg_write(UC_ARM_REG_LR,STOP)
    try:u.emu_start(sy['s3c_hsotg_probe'],STOP,count=3000000)
    except UcError:
        if not state['fault']:raise
    if variant=='T4_ANDROID_USB_01':
        assert state['fault'] and state['fault']['address']==0xc and state['fault']['PC']==0xc013bb64,state
    else:
        assert not state['fault'] and u.reg_read(UC_ARM_REG_PC)==STOP,state
        result=u.reg_read(UC_ARM_REG_R0);result=result if result<0x80000000 else result-0x100000000
        expect={'clock':-5,'irq':-16,'alloc':-12,'platform':-19,'id':-19,None:0}[fail];assert result==expect,(result,state)
        assert not state['mmio_before_clock'],state
        if not fail:assert state['irq']==1 and 10 in state['stages'],state
    return state
report={'old_actual_probe':execute('T4_ANDROID_USB_01'),'new_actual_probe':execute('T4_USB_ACM_01'),'clock_failure':execute('T4_USB_ACM_01','clock'),'irq_failure':execute('T4_USB_ACM_01','irq'),'allocation_failure':execute('T4_USB_ACM_01','alloc'),'missing_platform':execute('T4_USB_ACM_01','platform'),'inaccessible_ID':execute('T4_USB_ACM_01','id'),'hardware':'pending; injected IRQ and hardware registers are model fixtures, not a real device trace'}
(OUT/'irq-order-test.json').write_text(json.dumps(report,indent=2)+'\n');print('IRQ_ORDER_PASS: old PC c013bb64/NULL+0xc reproduced; new probe survives synchronous IRQ and error paths')
