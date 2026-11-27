#!/bin/sh
# Third-party code, outside Git: LVGL 8.4, ESP-Brookesia 0.4.2 and the apps of
# Espressif's phone example (both Apache-2.0).
set -eu
cd "$(dirname "$0")"
mkdir -p third_party
cd third_party
[ -d lvgl8 ] || git clone -q --depth 1 --branch v8.4.0 https://github.com/lvgl/lvgl lvgl8
[ -d esp-brookesia ] || git clone -q --depth 1 --branch v0.4.2 https://github.com/espressif/esp-brookesia
if [ ! -d brookesia-apps ]; then
	P=examples/esp32-p4-function-ev-board/examples/esp_brookesia_phone/components/apps
	rm -rf esp-dev-kits
	git clone -q --depth 1 --filter=blob:none --sparse https://github.com/espressif/esp-dev-kits
	git -C esp-dev-kits sparse-checkout set "$P"
	cp -r "esp-dev-kits/$P" brookesia-apps
	rm -rf esp-dev-kits
	# the music app: real files, real track lengths and ends (phone-ui/music/)
	patch -d brookesia-apps -p1 <../music.patch
fi
