"""Build the 2 KB C64 character set from the Misaki Gothic 2nd BDF (8x8 Japanese font by Num Kadoma).
Byte value == screen code: ASCII $21-$7E -> full-width forms, half-width kana $A1-$DF -> full-width kana."""
import os
import unicodedata

BDF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fonts', 'misaki_gothic_2nd.bdf')


def load_bdf(path):
    glyphs = {}; cur = None; bits = None; bbx = None
    for line in open(path, encoding='latin-1'):
        p = line.split()
        if not p: continue
        if p[0] == 'ENCODING': cur = int(p[1])
        elif p[0] == 'BBX': bbx = list(map(int, p[1:5]))
        elif p[0] == 'BITMAP': bits = []
        elif p[0] == 'ENDCHAR':
            w, h, xo, yo = bbx
            rows = [0] * 8
            top = 8 - yo - h          # font ascent 7, shifted down 1 dot: the top row stays blank
                                      # (the first text row starts on the raster split line)
            for i, v in enumerate(bits):
                y = top + i
                if 0 <= y < 8: rows[y] = (v >> xo) & 0xFF if xo >= 0 else (v << -xo) & 0xFF
            glyphs[cur] = rows; bits = None
        elif bits is not None:
            bits.append(int(p[0], 16))
    return glyphs


def build(path=BDF):
    g = load_bdf(path)
    data = bytearray(2048)
    for code in range(0x21, 0x7F):
        data[code * 8:code * 8 + 8] = bytes(g.get(0xFF01 + code - 0x21, [0] * 8))
    for code in range(0xA1, 0xE0):
        u = 0xFF61 + code - 0xA1
        ch = {0xFF9E: '゛', 0xFF9F: '゜'}.get(u) or unicodedata.normalize('NFKC', chr(u))
        data[code * 8:code * 8 + 8] = bytes(g.get(ord(ch), [0] * 8))
    data[0x7F * 8:0x7F * 8 + 8] = bytes([0x00, 0x20, 0x30, 0x38, 0x3C, 0x38, 0x30, 0x20])  # cursor arrow
    data[0x1F * 8:0x1F * 8 + 8] = bytes([0x00, 0x7E, 0x3C, 0x18, 0x00, 0x00, 0x00, 0x00])  # page-wait marker
    return bytes(data)
