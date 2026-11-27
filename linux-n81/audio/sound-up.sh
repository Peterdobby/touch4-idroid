#!/bin/sh
# Load the ALSA core, OSS emulation and the speaker driver.
[ -e /dev/dsp ] && exit 0
cd /lib/sound || exit 1
for m in soundcore snd snd-timer snd-pcm snd-mixer-oss snd-pcm-oss snd-n81; do
	insmod $m.ko || { echo "failed: $m"; exit 1; }
done
