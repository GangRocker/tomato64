"""Game description -> assembler data. Strings are written in half-width kana (cp932 single bytes)."""

OPS = {'end': 0, 'text': 1, 'set': 2, 'ifeq': 3, 'goto': 4, 'wait': 5, 'cls': 6, 'entry': 7, 'pic': 8}


# wording that only made sense with the original typed commands
TEXT_FIX = [('ﾃﾞﾊ CLEAR GAME ﾄ ｳﾁｺﾝﾀﾞ', 'ﾃﾞﾊ\nｼｽﾃﾑ ﾉ ﾛｰﾄﾞｶ ﾊｼﾞﾒｶﾗｦ ｴﾗﾝﾀﾞ'),
            ('CLEAR GAME ﾄ ｳﾁｺﾝﾀﾞ', 'ｼｽﾃﾑ ﾉ ﾛｰﾄﾞｶ ﾊｼﾞﾒｶﾗｦ ｴﾗﾝﾀﾞ')]


TRANSLATE = None             # translated build: {sha1 prefix of the original string: text}
CHARMAP = {}                 # extra characters of a translated build -> font codes


def key(s):
    import hashlib
    return hashlib.sha1(s.encode('utf-8')).hexdigest()[:16]


def kb(s):
    """half-width kana/ascii string -> bytes (newline = '\\n' -> 0x0d)."""
    if TRANSLATE is not None:
        k = key(s)
        if k not in TRANSLATE:
            raise KeyError('no translation for string %s (%d characters)' % (k, len(s)))
        s = TRANSLATE[k]
    else:
        for a, b in TEXT_FIX:
            s = s.replace(a, b)
    out = bytearray()
    for ch in s:
        if ch in CHARMAP:
            out.append(CHARMAP[ch])
        elif ch == '\n':
            out.append(0x0D)
        elif ord(ch) < 0x80:
            out.append(ord(ch))
        elif 0xFF61 <= ord(ch) <= 0xFF9F:
            out.append(ord(ch) - 0xFF61 + 0xA1)
        else:
            raise ValueError('not half-width kana: %r' % ch)
    return bytes(out)


def hexline(bs):
    return '        .byte ' + ','.join('$%02x' % x for x in bs) + '\n'


def rowtables(base=0x400):
    lo = ','.join('<(%d)' % (base + 40 * r) for r in range(25))
    hi = ','.join('>(%d)' % (base + 40 * r) for r in range(25))
    return 'rowlo:   .byte %s\nrowhi:   .byte %s\n' % (lo, hi)
