#!/usr/bin/env python3
"""Build the C64 version of "Salad no Kuni no Tomato-hime" from your own PC-9801 disk image.

usage: python3 build.py <disk.d88> [output_prefix] [--lang ja|en|es]

Produces <output_prefix>1.d64 and <output_prefix>2.d64 (default prefix: tomato_c64_ for Japanese,
tomato_c64_en_ / tomato_c64_es_ for the translations in lang/).
Only the Python 3 standard library is needed.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'tools'))

import source      # noqa: E402
import convert     # noqa: E402
import encode as E  # noqa: E402
import gamedata    # noqa: E402
import mkfont      # noqa: E402
import d64         # noqa: E402
import music       # noqa: E402
from asm6502 import Asm  # noqa: E402

# C64 palette (for the "nearest colour" preference table) and PC-9801 -> C64 colour mapping
C64_RGB = [(0, 0, 0), (255, 255, 255), (104, 55, 43), (112, 164, 178), (111, 61, 134), (88, 141, 67),
           (53, 40, 121), (184, 199, 111), (111, 79, 37), (67, 57, 0), (154, 103, 89), (68, 68, 68),
           (108, 108, 108), (154, 210, 132), (108, 94, 181), (149, 149, 149)]
PC2C64 = [0, 6, 2, 4, 5, 3, 7, 1]
NSCENES = 154


def disk_of(sid):
    # disk 1: scene groups B, C (0-76) + program; disk 2: groups D, A (77-153)
    return 1 if sid < 77 else 2


def vectables():
    pref = []
    for c in range(8):
        pref += sorted(range(8), key=lambda k: (sum((C64_RGB[PC2C64[c]][i] - C64_RGB[PC2C64[k]][i]) ** 2 for i in range(3)), k != c))
    rows = [0x8000 + 160 * y if y < 128 else 0xE000 + 160 * (y - 128) for y in range(168)]
    t = 'vrowlo: .byte ' + ','.join('<(%d)' % r for r in rows) + '\n'
    t += 'vrowhi: .byte ' + ','.join('>(%d)' % r for r in rows) + '\n'
    t += 'vpref: .byte ' + ','.join(map(str, pref)) + '\n'
    return t


def set_language(lang):
    """ja: original text. en/es: translation from lang/<lang>.json (word wrap, ROM Latin font, extra glyphs)."""
    if lang == 'ja':
        return {}
    data = json.load(open(os.path.join(HERE, 'lang', lang + '.json'), encoding='utf-8'))
    gamedata.TRANSLATE = data['strings']
    glyphs = data.get('glyphs', {})
    gamedata.CHARMAP = {ch: 0x80 + i for i, ch in enumerate(glyphs)}
    return {0x80 + i: g for i, g in enumerate(glyphs.values())}


def build(d88, prefix, log=print, lang='ja'):
    patch = set_language(lang)
    problems = source.load(d88)
    if problems:
        log('WARNING: this disk image differs from the one the converter was made for:')
        for p in problems: log('  ' + p)
        log('The build may fail or produce a broken game.')
    log('converting scenario ...')
    game = convert.convert_all(log)
    verbs, nouns = E.load_vocab()
    files = {}
    for sid in range(NSCENES):
        room = game.get(str(sid), dict(rules=[]))
        blob = E.build_room(room, sid, verbs, nouns)
        data = len(blob).to_bytes(2, 'little') + blob + source.picture(sid)
        assert len(data) <= 0x1000, ('room file too big', sid, len(data))
        files[sid] = bytes([0x00, 0x34]) + data          # loads at $3400
    log('assembling engine ...')
    font = bytearray(mkfont.build())
    for code, g in patch.items():
        font[code * 8:code * 8 + 8] = bytes(g)
    font = bytes(font)
    fontpath = os.path.join(HERE, 'build', 'font.bin')
    os.makedirs(os.path.dirname(fontpath), exist_ok=True)
    open(fontpath, 'wb').write(font)
    src = open(os.path.join(HERE, 'src', 'engine.asm')).read()
    if lang != 'ja':
        src = src.replace('WRAPON = 0', 'WRAPON = 1', 1)
    vr = open(os.path.join(HERE, 'src', 'vecrender.asm')).read()
    eq = ''.join(l + '\n' for l in vr.splitlines() if re.match(r'^\w+\s*=\s*\$', l))
    body = ''.join(l + '\n' for l in vr.splitlines() if not re.match(r'^\w+\s*=\s*\$', l))
    src = eq + src.replace(';@VECRENDER@', body + vectables())
    src = src.replace(';@ROWTABLES2@', gamedata.rowtables(0x4400))
    src = src.replace(';@GAMEDATA@', E.global_asm(verbs, nouns, E.INV, [disk_of(i) for i in range(NSCENES)]))
    src = src.replace(';@MUSIC@', music.asm(NSCENES))
    src += '\nfontdata:\n        .incbin "%s"\n' % fontpath
    a = Asm()
    org, code = a.assemble(src)
    prg = bytes([org & 0xFF, org >> 8]) + code
    disks = {1: [('TOMATOHIME', prg)], 2: []}
    for sid in range(NSCENES):
        disks[disk_of(sid)].append(('R%03d' % sid, files[sid]))
    for room, x in sorted(E.NEEDP):                       # event pictures shown from scripts
        lst = disks[disk_of(room)]
        name = 'P%03d' % x
        if name not in [n for n, _ in lst]:
            lst.append((name, bytes([0x00, 0x50]) + source.picture(x)))
    out = []
    for d, fl in sorted(disks.items()):
        path = '%s%d.d64' % (prefix, d)
        open(path, 'wb').write(d64.make_d64(fl, disk_name='TOMATOHIME', disk_id='D%d' % d))
        out.append(path)
        log('wrote %s (%d files)' % (path, len(fl)))
    return out


if __name__ == '__main__':
    args = sys.argv[1:]
    lang = 'ja'
    if '--lang' in args:
        i = args.index('--lang')
        lang = args[i + 1]
        del args[i:i + 2]
    if not args or lang not in ('ja', 'en', 'es'):
        print(__doc__)
        sys.exit(1)
    build(args[0], args[1] if len(args) > 1 else ('tomato_c64_' if lang == 'ja' else 'tomato_c64_%s_' % lang), lang=lang)
