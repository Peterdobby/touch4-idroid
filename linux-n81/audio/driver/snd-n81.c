// SPDX-License-Identifier: GPL-2.0
/*
 * Speaker playback for the iPod touch 4G (N81AP): CS42L59 codec on I2C, I2S0,
 * CDMA channel 0x1a. Playback only, S16_LE stereo at 44.1 kHz, speaker only.
 *
 * Codec and I2S values are the writes iOS 6.1.6 makes, traced under qemu-ios;
 * the CDMA register and descriptor layout follows its hw/arm/s5l8930_cdma.c.
 * Descriptors form a ring that the engine follows until it is aborted; period
 * notifications come from a timer, so no DMA interrupt is used.
 */
#include <linux/delay.h>
#include <linux/dma-mapping.h>
#include <linux/hrtimer.h>
#include <linux/i2c.h>
#include <linux/io.h>
#include <linux/iopoll.h>
#include <linux/module.h>
#include <linux/platform_device.h>
#include <sound/control.h>
#include <sound/core.h>
#include <sound/initval.h>
#include <sound/pcm.h>
#include <sound/tlv.h>

#define I2S_PHYS	0x84500400
#define I2S_TX_FIFO	0x10
#define CDMA_PHYS	0x87000000
#define CDMA_CH		0x1a
#define PMGR_I2S_GATE	0xbf101094
#define GPIO_SPEAKER	(0xbfa00000 + 161 * 4)
#define CODEC_ADDR	0x4a
/* DMA masters see DRAM here; the CPU has it at 0. */
#define DRAM_BUS	0x40000000u

#define CH_CTRL		0x00
#define CH_SETTINGS	0x04
#define CH_FIFO		0x08
#define CH_REMAIN	0x0c
#define CH_ADDR		0x10
#define CH_DESC		0x14
#define CH_ERROR	0x18
/* bit 3, the DMA interrupt, stays off: nothing handles it */
#define CTRL_GO		0x11
#define CTRL_ABORT	0x14
#define CTRL_RESET	0x02
#define CTRL_ABORTED	0x200000
/* to device, 16-bit accesses, the burst and peripheral id of i2s0 TX */
#define SETTINGS_I2S0_TX 0x000400a6
#define DESC_DATA	0x3

#define MAX_PERIODS	64
#define BUFFER_MAX	(128 * 1024)
/* codec output volume in half dB; iOS never goes above -4 dB on the speaker */
#define VOL_MIN		(-60)
#define VOL_MAX		(-8)
#define VOL_DEFAULT	(-20)

struct cdma_desc {
	__le32 next, flags, addr, len, priv[4];
};

struct n81 {
	struct i2c_adapter *i2c;
	void __iomem *i2s, *cdma, *gate, *gpio;
	struct snd_card *card;
	struct snd_pcm_substream *substream;
	struct cdma_desc *desc;
	dma_addr_t desc_dma;
	struct hrtimer timer;
	ktime_t period;
	bool running;
	int volume;
	bool unmuted;
};

static struct platform_device *n81_pdev;


static const u8 startup[][2] = {
	{0x3b, 0xa5}, {0x3b, 0x00}, {0x07, 0x00}, {0x09, 0x20}, {0x09, 0x20},
	{0x0a, 0x0b}, {0x31, 0x80}, {0x1a, 0x00}, {0x0e, 0xc0}, {0x0e, 0xc8},
	{0x32, 0x8f}, {0x0c, 0xc0}, {0x1a, 0x01}, {0x10, 0x01}, {0x0e, 0xd8},
	{0x1d, 0x40}, {0x1f, 0x40}, {0x21, 0x40}, {0x06, 0x00}, {0x07, 0x3f},
	{0x1d, 0x40}, {0x1f, 0x40}, {0x21, 0x40}, {0x2a, 0x27}, {0x2b, 0x27},
	{0x06, 0x20}, {0x10, 0xc1}, {0x11, 0x18}, {0x13, 0x00}, {0x0c, 0xcf},
	{0x07, 0xff}, {0x2c, 0x27}, {0x2d, 0x27}, {0x28, 0x27}, {0x29, 0x27},
	{0x06, 0x20}, {0x0a, 0x00}, {0x1b, 0x00}, {0x1c, 0x00}, {0x07, 0xff},
	{0x1d, 0x40}, {0x1f, 0x40}, {0x21, 0x40}, {0x07, 0xff}, {0x35, 0x00},
	{0x36, 0x80}, {0x37, 0xff}, {0x08, 0x01}, {0x06, 0x38}, {0x06, 0xb8},
	{0x30, 0x02}, {0x35, 0x00}, {0x36, 0x80}, {0x37, 0xff}, {0x0a, 0x0b},
};
static const u8 playback[][2] = {
	{0x07, 0xfc}, {0x1d, 0x40}, {0x1f, 0x40}, {0x21, 0x78}, {0x2a, 0x00},
	{0x2b, 0x00}, {0x06, 0xb8},
};
static const u8 stop[][2] = {
	{0x07, 0xff}, {0x21, 0x40}, {0x2a, 0x27}, {0x2b, 0x27},
};

static int codec_write(struct n81 *n, u8 reg, u8 val)
{
	u8 b[2] = { reg, val };
	struct i2c_msg m = { .addr = CODEC_ADDR, .len = 2, .buf = b };
	int ret = i2c_transfer(n->i2c, &m, 1);

	return ret == 1 ? 0 : ret < 0 ? ret : -EIO;
}

static int codec_apply(struct n81 *n, const u8 (*t)[2], unsigned int count)
{
	unsigned int i;
	int ret;

	for (i = 0; i < count; i++) {
		ret = codec_write(n, t[i][0], t[i][1]);
		if (ret)
			return ret;
		if (t[i][0] == 0x3b)
			usleep_range(10000, 11000);
	}
	return 0;
}

static int codec_volume(struct n81 *n)
{
	return codec_write(n, 0x21, n->unmuted ? n->volume & 0x7f : 0x40);
}

static void n81_stop(struct n81 *n)
{
	void __iomem *ch = n->cdma + CDMA_CH * 0x1000;
	u32 val;

	writel(0, n->i2s + 0x08);
	writel(0x202, n->gpio);
	writel(CTRL_ABORT, ch + CH_CTRL);
	if (readl_poll_timeout_atomic(ch + CH_CTRL, val, val & CTRL_ABORTED, 1, 1000))
		pr_warn("snd-n81: DMA did not stop, ctrl %08x\n", val);
	writel(CTRL_RESET, ch + CH_CTRL);
	writel(0x1a0, n->i2s);
	writel(0x20000300, n->i2s + 0x410);
}

static void n81_start(struct n81 *n)
{
	void __iomem *ch = n->cdma + CDMA_CH * 0x1000;

	writel(BIT(CDMA_CH), n->cdma);			/* before any access */
	writel(CTRL_RESET, ch + CH_CTRL);
	writel(SETTINGS_I2S0_TX, ch + CH_SETTINGS);
	writel(I2S_PHYS + I2S_TX_FIFO, ch + CH_FIFO);
	writel(0x40000000, ch + CH_REMAIN);
	writel(n->desc_dma + DRAM_BUS, ch + CH_DESC);

	writel(0x28000300, n->i2s + 0x410);		/* codec master clock */
	writel(1, n->i2s + 0x3c);
	writel(0x03100099, n->i2s + 0x04);
	writel(0x1000, n->i2s + 0x30);
	writel(0, n->i2s + 0x08);
	writel(0, n->i2s + 0x34);
	writel(0, n->i2s + 0x40);
	writel(0x181, n->i2s);

	wmb();
	writel(CTRL_GO, ch + CH_CTRL);			/* queue data first */
	writel(6, n->i2s + 0x08);
	writel(0x203, n->gpio);
}

static enum hrtimer_restart n81_tick(struct hrtimer *timer)
{
	struct n81 *n = container_of(timer, struct n81, timer);

	if (!READ_ONCE(n->running))
		return HRTIMER_NORESTART;
	snd_pcm_period_elapsed(n->substream);
	hrtimer_forward_now(timer, n->period);
	return HRTIMER_RESTART;
}

static const struct snd_pcm_hardware n81_hw = {
	.info = SNDRV_PCM_INFO_MMAP | SNDRV_PCM_INFO_MMAP_VALID |
		SNDRV_PCM_INFO_INTERLEAVED | SNDRV_PCM_INFO_BLOCK_TRANSFER,
	.formats = SNDRV_PCM_FMTBIT_S16_LE,
	.rates = SNDRV_PCM_RATE_44100,
	.rate_min = 44100,
	.rate_max = 44100,
	.channels_min = 2,
	.channels_max = 2,
	.buffer_bytes_max = BUFFER_MAX,
	.period_bytes_min = 1024,
	.period_bytes_max = BUFFER_MAX / 2,
	.periods_min = 2,
	.periods_max = MAX_PERIODS,
};

static int n81_open(struct snd_pcm_substream *s)
{
	struct n81 *n = snd_pcm_substream_chip(s);
	int ret;

	s->runtime->hw = n81_hw;
	ret = snd_pcm_hw_constraint_step(s->runtime, 0,
					 SNDRV_PCM_HW_PARAM_PERIOD_BYTES, 32);
	if (ret < 0)
		return ret;
	ret = snd_pcm_hw_constraint_integer(s->runtime, SNDRV_PCM_HW_PARAM_PERIODS);
	if (ret < 0)
		return ret;
	n->substream = s;
	return 0;
}

static int n81_close(struct snd_pcm_substream *s)
{
	struct n81 *n = snd_pcm_substream_chip(s);

	hrtimer_cancel(&n->timer);
	return 0;
}

static int n81_prepare(struct snd_pcm_substream *s)
{
	struct n81 *n = snd_pcm_substream_chip(s);
	struct snd_pcm_runtime *r = s->runtime;
	unsigned int bytes = snd_pcm_lib_period_bytes(s), i;
	int ret;

	hrtimer_cancel(&n->timer);
	for (i = 0; i < r->periods; i++) {
		struct cdma_desc *d = &n->desc[i];
		unsigned int next = (i + 1) % r->periods;

		d->next = cpu_to_le32(n->desc_dma + DRAM_BUS + next * sizeof(*d));
		d->flags = cpu_to_le32(DESC_DATA);
		d->addr = cpu_to_le32(r->dma_addr + DRAM_BUS + i * bytes);
		d->len = cpu_to_le32(bytes);
	}
	n->period = ns_to_ktime(div_u64((u64)r->period_size * NSEC_PER_SEC, r->rate));
	ret = codec_apply(n, startup, ARRAY_SIZE(startup));
	if (!ret)
		ret = codec_apply(n, playback, ARRAY_SIZE(playback));
	if (ret)
		return ret;
	n->unmuted = true;
	return codec_volume(n);
}

static int n81_hw_free(struct snd_pcm_substream *s)
{
	struct n81 *n = snd_pcm_substream_chip(s);

	hrtimer_cancel(&n->timer);
	n->unmuted = false;
	codec_write(n, 0x07, 0xff);
	codec_volume(n);
	return 0;
}

static int n81_trigger(struct snd_pcm_substream *s, int cmd)
{
	struct n81 *n = snd_pcm_substream_chip(s);

	switch (cmd) {
	case SNDRV_PCM_TRIGGER_START:
		n81_start(n);
		WRITE_ONCE(n->running, true);
		hrtimer_start(&n->timer, n->period, HRTIMER_MODE_REL_SOFT);
		return 0;
	case SNDRV_PCM_TRIGGER_STOP:
		WRITE_ONCE(n->running, false);
		n81_stop(n);
		return 0;
	}
	return -EINVAL;
}

static snd_pcm_uframes_t n81_pointer(struct snd_pcm_substream *s)
{
	struct n81 *n = snd_pcm_substream_chip(s);
	u32 pos = readl(n->cdma + CDMA_CH * 0x1000 + CH_ADDR) -
		  (u32)(s->runtime->dma_addr + DRAM_BUS);

	if (pos >= snd_pcm_lib_buffer_bytes(s))
		pos = 0;
	return bytes_to_frames(s->runtime, pos);
}

static const struct snd_pcm_ops n81_ops = {
	.open = n81_open,
	.close = n81_close,
	.prepare = n81_prepare,
	.hw_free = n81_hw_free,
	.trigger = n81_trigger,
	.pointer = n81_pointer,
};

static int n81_vol_info(struct snd_kcontrol *k, struct snd_ctl_elem_info *i)
{
	i->type = SNDRV_CTL_ELEM_TYPE_INTEGER;
	i->count = 1;
	i->value.integer.min = 0;
	i->value.integer.max = VOL_MAX - VOL_MIN;
	return 0;
}

static int n81_vol_get(struct snd_kcontrol *k, struct snd_ctl_elem_value *v)
{
	struct n81 *n = snd_kcontrol_chip(k);

	v->value.integer.value[0] = n->volume - VOL_MIN;
	return 0;
}

static int n81_vol_put(struct snd_kcontrol *k, struct snd_ctl_elem_value *v)
{
	struct n81 *n = snd_kcontrol_chip(k);
	long val = v->value.integer.value[0];

	if (val < 0 || val > VOL_MAX - VOL_MIN)
		return -EINVAL;
	if (val + VOL_MIN == n->volume)
		return 0;
	n->volume = val + VOL_MIN;
	if (n->unmuted)
		codec_volume(n);
	return 1;
}

static const DECLARE_TLV_DB_SCALE(n81_tlv, VOL_MIN * 50, 50, 0);

static const struct snd_kcontrol_new n81_volume = {
	.iface = SNDRV_CTL_ELEM_IFACE_MIXER,
	.name = "Speaker Playback Volume",
	.access = SNDRV_CTL_ELEM_ACCESS_READWRITE | SNDRV_CTL_ELEM_ACCESS_TLV_READ,
	.info = n81_vol_info,
	.get = n81_vol_get,
	.put = n81_vol_put,
	.tlv = { .p = n81_tlv },
};

static int n81_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct snd_card *card;
	struct snd_pcm *pcm;
	struct n81 *n;
	int ret;

	ret = dma_coerce_mask_and_coherent(dev, DMA_BIT_MASK(32));
	if (ret)
		return ret;
	ret = snd_devm_card_new(dev, SNDRV_DEFAULT_IDX1, "N81", THIS_MODULE,
				sizeof(*n), &card);
	if (ret)
		return ret;
	n = card->private_data;
	n->card = card;
	n->volume = VOL_DEFAULT;
	/* Plain mappings: the pin and clock blocks belong to other drivers. */
	n->i2s = devm_ioremap(dev, I2S_PHYS, 0xc00);
	n->cdma = devm_ioremap(dev, CDMA_PHYS, (CDMA_CH + 1) * 0x1000);
	n->gate = devm_ioremap(dev, PMGR_I2S_GATE, 4);
	n->gpio = devm_ioremap(dev, GPIO_SPEAKER, 4);
	if (!n->i2s || !n->cdma || !n->gate || !n->gpio)
		return -ENOMEM;
	n->desc = dmam_alloc_coherent(dev, MAX_PERIODS * sizeof(*n->desc),
				      &n->desc_dma, GFP_KERNEL);
	if (!n->desc)
		return -ENOMEM;
	/* the I2S block hangs the bus if touched while gated */
	writel(readl(n->gate) | 0xf, n->gate);
	ret = readl_poll_timeout(n->gate, ret, (ret & 0xf0) == 0xf0, 100, 100000);
	if (ret)
		return dev_err_probe(dev, ret, "I2S clock gate\n");
	n->i2c = i2c_get_adapter(0);
	if (!n->i2c)
		return -EPROBE_DEFER;
	hrtimer_setup(&n->timer, n81_tick, CLOCK_MONOTONIC, HRTIMER_MODE_REL_SOFT);

	strscpy(card->driver, "snd-n81");
	strscpy(card->shortname, "iPod touch 4G");
	strscpy(card->longname, "iPod touch 4G speaker (CS42L59)");
	ret = snd_pcm_new(card, "speaker", 0, 1, 0, &pcm);
	if (ret)
		goto err;
	pcm->private_data = n;
	strscpy(pcm->name, "speaker");
	snd_pcm_set_ops(pcm, SNDRV_PCM_STREAM_PLAYBACK, &n81_ops);
	snd_pcm_set_managed_buffer_all(pcm, SNDRV_DMA_TYPE_DEV, dev,
				       BUFFER_MAX, BUFFER_MAX);
	ret = snd_ctl_add(card, snd_ctl_new1(&n81_volume, n));
	if (ret)
		goto err;
	ret = snd_card_register(card);
	if (ret)
		goto err;
	platform_set_drvdata(pdev, n);
	return 0;
err:
	i2c_put_adapter(n->i2c);
	return ret;
}

static void n81_remove(struct platform_device *pdev)
{
	struct n81 *n = platform_get_drvdata(pdev);

	snd_card_disconnect_sync(n->card);
	i2c_put_adapter(n->i2c);
}

static struct platform_driver n81_driver = {
	.probe = n81_probe,
	.remove = n81_remove,
	.driver = { .name = "snd-n81" },
};

static int __init n81_init(void)
{
	int ret = platform_driver_register(&n81_driver);

	if (ret)
		return ret;
	/* no device tree node: the board is known, so create the device here */
	n81_pdev = platform_device_register_simple("snd-n81", -1, NULL, 0);
	if (IS_ERR(n81_pdev)) {
		platform_driver_unregister(&n81_driver);
		return PTR_ERR(n81_pdev);
	}
	return 0;
}
module_init(n81_init);

static void __exit n81_exit(void)
{
	platform_device_unregister(n81_pdev);
	platform_driver_unregister(&n81_driver);
}
module_exit(n81_exit);

MODULE_DESCRIPTION("iPod touch 4G speaker playback");
MODULE_LICENSE("GPL");
