#!/bin/sh
# Read audio-related state without changing it, to capture what iOS left behind.
# Run first thing after boot. Needs mem and i2c-peek as /tmp/mem and /tmp/peek.
r() { /tmp/mem $1 | awk '{print $1 "=" $3}'; }
block() { # start end(inclusive)
	i=$(($1))
	while [ $i -le $(($2)) ]; do r $(printf '0x%x' $i); i=$((i+4)); done
}
echo "== codec"; /tmp/peek 0x4a 0 128
echo "== nco"; block 0xbf100100 0xbf10013c
echo "== clocks"; block 0xbf100040 0xbf1000fc
echo "== gates"; block 0xbf101080 0xbf10109c
echo "== gpio"; block 0xbfa00000 0xbfa002bc
gate=$(/tmp/mem 0xbf101094 | awk '{print $3}')
# reading a gated block can hang the machine: open the gate first
/tmp/mem 0xbf101094 $((gate | 0xf)) >/dev/null
echo "== i2s0 (gate was $gate)"; block 0x84500400 0x84500448
