#!/usr/bin/env python3
"""icons.py UI_IMAGES_DIR OUT.c: the Setting icons come in 16-bit colour only; write
them in grey, with their alpha, in LVGL's 32-bit format. The back arrow, black in
the original light theme, comes out white."""
import pathlib, re, sys

source, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
text = '#include "lvgl.h"\n'
for name in 'wifi bluetooth sound light about arrow return'.split():
    symbol = f'ui_img_{name}_png'
    c = (source / f'{symbol}.c').read_text()
    data = [int(x, 16) for x in re.findall(r'0x[0-9A-Fa-f]{2}', c.split('_data[]')[1].split('};')[0])]
    w, h = (int(re.search(rf'\.header\.{k} = (\d+)', c)[1]) for k in 'wh')
    assert len(data) == w * h * 3, symbol
    def grey(lo, hi):
        if name == 'return':
            return 255
        v = lo | hi << 8
        return round(0.299 * (v >> 11) * 255 / 31 + 0.587 * (v >> 5 & 63) * 255 / 63 +
                     0.114 * (v & 31) * 255 / 31)
    pixels = ','.join(f'{g},{g},{g},{a}' for lo, hi, a in zip(data[::3], data[1::3], data[2::3])
                      for g in [grey(lo, hi)])
    text += (f'static const uint8_t {name}_map[] = {{{pixels}}};\n'
             f'const lv_img_dsc_t {symbol} = {{ .header.cf = LV_IMG_CF_TRUE_COLOR_ALPHA, '
             f'.header.w = {w}, .header.h = {h}, .data_size = sizeof({name}_map), .data = {name}_map }};\n')
out.write_text(text)
