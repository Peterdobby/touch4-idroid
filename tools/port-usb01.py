"""Apply the USB01 experiment to its isolated kernel only; baseline untouched."""
from pathlib import Path
r=Path(__file__).resolve().parent.parent;src=r/'saved/sources/iDroid-kernel-T4_ANDROID_USB_01'
p=src/'drivers/usb/gadget/s3c-hsotg.c';s=p.read_text();assert '#include <mach/t4_usb.h>' not in s
s=s.replace('#include <mach/map.h>','#include <mach/map.h>\n#include <mach/t4_usb.h>')
s=s.replace('static void s3c_hsotg_init_fifo(','static int s3c_hsotg_init_fifo(')
a=s.index('\t/* set FIFO sizes to 2048/1024 */');b=s.index('\t/* according to p428',a)
s=s[:a]+'''#ifdef CONFIG_CPU_S5L8930
    /* N81 observed HWCFG3=07e800e8: 2024 words total, not 16K.
     * RX512 + EP0 TX128 + 8 TX128 = 1664 words. */
    val=readl(hsotg->regs+0x4c)>>16;
    if(val<1664) { t4_usb_stage(-ENOSPC);return -ENOSPC; }
    writel(512,hsotg->regs+S3C_GRXFSIZ);
    writel(S3C_GNPTXFSIZ_NPTxFStAddr(512)|S3C_GNPTXFSIZ_NPTxFDep(128),hsotg->regs+S3C_GNPTXFSIZ);
    addr=640;size=128;
    for(ep=1;ep<S3C_HSOTG_EPS;ep++) {
        writel(addr|(size<<16),hsotg->regs+S3C_DPTXFSIZn(ep));addr+=size;
    }
#else
'''+s[a:b]+'''#endif
'''+s[b:]
a=s.index('static int s3c_hsotg_init_fifo(');b=s.index('\n}',a);part=s[a:b].replace('timeout = 100;','timeout = 1000;').replace('if (--timeout == 0) {','if (--timeout == 0) {\n            t4_usb_stage(-ETIMEDOUT);return -ETIMEDOUT;');s=s[:a]+part+'\n    return 0;'+s[b:]
a=s.index('static void s3c_hsotg_txfifo_flush(');b=s.index('\n}',a);part=s[a:b].replace('if (--timeout == 0) {','if (--timeout == 0) {\n            t4_usb_stage(-ETIMEDOUT);return;');s=s[:a]+part+s[b:]
s=s.replace('irq_retry:\n','    t4_usb_irq_tick();\nirq_retry:\n',1)
s=s.replace('ep < 15 && daint_out','ep < S3C_HSOTG_EPS && daint_out').replace('ep < 15 && daint_in','ep < S3C_HSOTG_EPS && daint_in')
s=s.replace('\tep0->sent_zlp = 0;','\tt4_usb_setup_tick();\n\tep0->sent_zlp = 0;',1)
a=s.index('static int s3c_hsotg_corereset(');b=s.index('\n}',a);part=s[a:b].replace('timeout = 1000;','timeout = 10000;').replace('grstctl = readl(hsotg->regs + S3C_GRSTCTL);','grstctl = readl(hsotg->regs + S3C_GRSTCTL);\n        udelay(1);');s=s[:a]+part+s[b:]
a=s.index('static void s3c_hsotg_otgreset(');b=s.index('\n}',a)
s=s[:a]+'''static noinline int s3c_hsotg_otgreset(struct s3c_hsotg *hsotg)
{
#ifdef CONFIG_CPU_S5L8930
    struct clk *reference;
    unsigned long rate;
    u32 select;
    reference=clk_get(hsotg->dev,"xusbxti");
    if(IS_ERR(reference)) return PTR_ERR(reference);
    rate=clk_get_rate(reference);clk_put(reference);
    if(rate==12000000) select=0;
    else if(rate==24000000) select=1;
    else if(rate==48000000) select=2;
    else return -EINVAL;
    /* Restore the stop bits left by OpeniBoot shutdown, no other bits. */
    writel(readl(hsotg->regs+0xe00)&~3u,hsotg->regs+0xe00);
    writel(0x200,S3C_HSOTG_PHYREG(0x60));
    writel(6,S3C_PHYPWR);
    writel(6,S3C_HSOTG_PHYREG(0x1c));
    writel(0x733,S3C_HSOTG_PHYREG(0x44));udelay(10);
    writel((readl(S3C_PHYCLK)&~3u)|select,S3C_PHYCLK);
    writel(readl(S3C_RSTCON)|1,S3C_RSTCON);udelay(20);
    writel(readl(S3C_RSTCON)&~1u,S3C_RSTCON);udelay(1000);
    dev_info(hsotg->dev,"T4_USB A4 PHY rate=%lu select=%u\\n",rate,select);
    return 0;
#else
'''+s[a:b].split('{',1)[1]+'''\n    return 0;
#endif
}'''+s[b+2:]
s=s.replace('static void s3c_hsotg_init(','static int s3c_hsotg_init(')
a=s.index('static int s3c_hsotg_init(');b=s.index('\n}',a);part=s[a:b].replace('\tu32 cfg4;','\tu32 cfg4;\n    int ret;').replace('\ts3c_hsotg_init_fifo(hsotg);','\tret=s3c_hsotg_init_fifo(hsotg);\n    if(ret) return ret;');s=s[:a]+part+'\n    return 0;'+s[b:]
a=s.index('int usb_gadget_probe_driver(');b=s.index('EXPORT_SYMBOL(usb_gadget_probe_driver)',a);part=s[a:b]
part=part.replace('\ts3c_hsotg_corereset(hsotg);','\tret=s3c_hsotg_corereset(hsotg);\n    if(ret) goto err_bound;').replace('\ts3c_hsotg_init_fifo(hsotg);','\tret=s3c_hsotg_init_fifo(hsotg);\n    if(ret) goto err_bound;')
part=part.replace('\t__bic32(hsotg->regs + S3C_DCTL, S3C_DCTL_SftDiscon);','#ifndef CONFIG_CPU_S5L8930\n\t__bic32(hsotg->regs + S3C_DCTL, S3C_DCTL_SftDiscon);\n#endif')
part=part.replace('\treturn 0;\n\nerr:', '\tt4_usb_stage(20);\n\treturn 0;\n\nerr_bound:\n    t4_usb_stage(ret);\n    if(driver->unbind) driver->unbind(&hsotg->gadget);\n    device_del(&hsotg->gadget.dev);\nerr:');s=s[:a]+part+s[b:]
a=s.index('static struct usb_gadget_ops s3c_hsotg_gadget_ops')
s=s[:a]+'''static int s3c_hsotg_pullup(struct usb_gadget *g,int on)
{
    struct s3c_hsotg *h=to_hsotg(g);
    if(on) __bic32(h->regs+S3C_DCTL,S3C_DCTL_SftDiscon);
    else __orr32(h->regs+S3C_DCTL,S3C_DCTL_SftDiscon);
    return 0;
}

'''+s[a:]
s=s.replace('.get_frame\t= s3c_hsotg_gadget_getframe,','.get_frame\t= s3c_hsotg_gadget_getframe,\n    .pullup = s3c_hsotg_pullup,')
a=s.index('static int __devinit s3c_hsotg_probe(');b=s.index('static int __devexit s3c_hsotg_remove',a);part=s[a:b]
part=part.replace('\tint ret;','\tint ret;\n    int irq_requested=0,clock_on=0;\n    t4_usb_stage(1);',1)
part=part.replace('\tdev_info(dev, "regs %p, irq %d\\n",', '\tirq_requested=1;disable_irq(hsotg->irq);\n\tdev_info(dev, "regs %p, irq %d\\n",')
part=part.replace('\tclk_enable(hsotg->clk);','\tret=clk_enable(hsotg->clk);\n    if(ret) goto err_regs;\n    clock_on=1;t4_usb_stage(2);')
part=part.replace('\ts3c_hsotg_otgreset(hsotg);\n\ts3c_hsotg_corereset(hsotg);\n\ts3c_hsotg_init(hsotg);','\tret=s3c_hsotg_otgreset(hsotg);\n    if(ret) goto err_regs;\n    t4_usb_stage(3);\n\tret=s3c_hsotg_corereset(hsotg);\n    if(ret) goto err_regs;\n    t4_usb_stage(4);\n\tret=s3c_hsotg_init(hsotg);\n    if(ret) goto err_regs;')
part=part.replace('\tour_hsotg = hsotg;','\tour_hsotg = hsotg;\n    enable_irq(hsotg->irq);t4_usb_stage(10);')
part=part.replace('err_regs:\n','err_regs:\n    t4_usb_stage(ret);\n    if(irq_requested) free_irq(hsotg->irq,hsotg);\n    if(clock_on) clk_disable(hsotg->clk);\n');s=s[:a]+part+s[b:]
s=s.replace('\t\ts3c_hsotg_init_fifo(hsotg);','\t\tif(s3c_hsotg_init_fifo(hsotg)) {\n            writel(0,hsotg->regs+S3C_GAHBCFG);return IRQ_HANDLED;\n        }')
p.write_text(s)
p=src/'drivers/usb/gadget/android.c';s=p.read_text().replace('#include <linux/module.h>','#include <linux/module.h>\n#include <mach/t4_usb.h>');a=s.index('static struct android_usb_function *supported_functions[]');b=s.index('\n};',a);s=s[:a]+'''static struct android_usb_function *supported_functions[] = {
    &adb_function,
    NULL'''+s[b:]
s=s.replace('\tint enabled = 0;','\tint enabled = 0;\n    int ret;').replace('\t\tusb_add_config(cdev, &android_config_driver,\n\t\t\t\t\tandroid_bind_config);','\t\tret=usb_add_config(cdev, &android_config_driver,android_bind_config);\n        if(ret) { t4_usb_stage(ret);return ret; }')
s=s.replace('\t\tusb_gadget_connect(cdev->gadget);','\t\tret=usb_gadget_connect(cdev->gadget);\n        if(ret) { usb_remove_config(cdev,&android_config_driver);t4_usb_stage(ret);return ret; }');a=s.index('static ssize_t enable_store(');b=s.index('static ssize_t state_show',a);part=s[a:b].replace('\tsscanf(buff, \"%d\", &enabled);','\tif(!cdev) return -ENODEV;\n\tsscanf(buff, \"%d\", &enabled);');s=s[:a]+part+s[b:];p.write_text(s)
p=src/'drivers/usb/gadget/f_adb.c';s=p.read_text().replace('#include <linux/module.h>','#include <linux/module.h>\n#include <mach/t4_usb.h>')
s=s.replace('\t_adb_dev->error = 0;','\t_adb_dev->error = 0;\n    t4_usb_adb_flag(1,1);',1).replace('\tadb_unlock(&_adb_dev->open_excl);','\tt4_usb_adb_flag(1,0);\n\tadb_unlock(&_adb_dev->open_excl);',1)
s=s.replace('\tdev->online = 1;','\tdev->online = 1;\n    t4_usb_adb_flag(2,1);').replace('\tdev->online = 0;','\tdev->online = 0;\n    t4_usb_adb_flag(2,0);');p.write_text(s)
print('USB01 driver patch applied to isolated source')
