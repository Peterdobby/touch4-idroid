#!/bin/sh
# Play a short scale through the ALSA driver. Run from the menu.
[ -e /dev/dsp ] || sound-up || exit 1
n81-play -v 60
echo "scale"
n81-play -t && echo "done"
