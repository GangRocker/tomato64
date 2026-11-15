"""Read the PC-9801 disk image (D88, N88-BASIC(86) 2HD format) and expose the game files.

Nothing from the game is stored in this repository: everything is extracted from the user's own disk image.
"""
import struct
import zlib

# CRC32 of the game files this converter was written against
KNOWN = {
    'SARADAP0': 0xca1acb16,
    'SARADAP1': 0xff3f6465,
    'SARADAP2': 0x75a17343,
    'SARADAP3': 0xda67b1cb,
    'SARADAP4': 0x9490b213,
}
# region (scene group) -> file; each file loads at segment offset $3000
REGION_FILE = {'B': 'SARADAP1', 'C': 'SARADAP2', 'D': 'SARADAP3', 'A': 'SARADAP4'}

MEM = None      # region -> 64 KB memory image
FILES = None    # name -> bytes (without the 4-byte load header)


def linear_dump(d88):
    """D88 -> linear bytes in cylinder/head/sector order."""
    offs = struct.unpack_from('<164I', d88, 0x20)
    out = bytearray()
    for o in offs:
        if not o:
            continue
        n = struct.unpack_from('<H', d88, o + 4)[0]
        secs = []
        p = o
        for _ in range(n):
            r = d88[p + 2]
            size = struct.unpack_from('<H', d88, p + 14)[0]
            secs.append((r, d88[p + 16:p + 16 + size]))
            p += 16 + size
        for r, data in sorted(secs):
            out += data
    return bytes(out)


def n88_files(dump):
    """N88-BASIC(86) 2HD: directory = cylinder 35 head 0 (track 70), FAT = sector 24 of that track.
    One cluster = one track side (26 x 256 bytes); track 0 side 0 has 128-byte sectors (3328 bytes)."""
    def trk(c):
        return c * 6656 - 3328
    base = trk(70)
    fat = dump[base + 23 * 256:base + 24 * 256]
    files = {}
    for i in range(0, 12 * 256, 16):
        e = dump[base + i:base + i + 16]
        if e[0] in (0, 0xFF):
            continue
        name = (e[:6].decode('ascii', 'replace').strip() + e[6:9].decode('ascii', 'replace').strip())
        c = e[10]
        chain = []
        while True:
            chain.append(c)
            nx = fat[c]
            if nx >= 0xC0:
                last = nx - 0xC0
                break
            c = nx
        data = b''.join(dump[trk(k):trk(k) + 6656] for k in chain[:-1]) + dump[trk(chain[-1]):trk(chain[-1]) + last * 256]
        files[name] = data
    return files


# The original Hudson release is a self-booting 2DD disk (16 x 256-byte sectors per track). The game only uses
# every fourth track (cylinder 2n, side 0): those tracks form a 160 KB "logical" disk. Region files are stored as
# whole logical tracks and load at $3000.
LAYOUT_2DD = {'B': (3, 11), 'C': (14, 6), 'D': (20, 8), 'A': (28, 11)}     # region -> (first logical track, count)
KNOWN_2DD = {'B': 0x616c4fb8, 'C': 0x4df9a0ae, 'D': 0x3a107e6c, 'A': 0xbfe3fc6a}


def load(path):
    """Load either the original 2DD disk image or the 2HD N88-BASIC copy. Returns a list of problems found."""
    global MEM, FILES
    d88 = open(path, 'rb').read()
    lin = linear_dump(d88)
    problems = []
    try:
        files = n88_files(lin)
    except Exception:
        files = {}
    if all(n in files for n in KNOWN):
        for name, crc in KNOWN.items():
            got = zlib.crc32(files[name]) & 0xFFFFFFFF
            if got != crc:
                problems.append('%s: CRC %08x (expected %08x)' % (name, got, crc))
        FILES = {k: v[4:] for k, v in files.items()}
        regions = {r: FILES[fn] for r, fn in REGION_FILE.items()}
    else:
        if len(lin) < 160 * 0x1000:
            raise ValueError('not a Salad no Kuni no Tomato-hime disk image (unknown format)')
        logical = b''.join(lin[t * 0x1000:(t + 1) * 0x1000] for t in range(0, 160, 4))
        regions = {r: logical[a * 0x1000:(a + n) * 0x1000] for r, (a, n) in LAYOUT_2DD.items()}
        for r, crc in KNOWN_2DD.items():
            got = zlib.crc32(regions[r]) & 0xFFFFFFFF
            if got != crc:
                problems.append('region %s: CRC %08x (expected %08x)' % (r, got, crc))
        FILES = {'SARADAP0': lin}            # the word list is searched for, its exact position does not matter
    MEM = {}
    for r, body in regions.items():
        m = bytearray(0x10000)
        m[0x3000:0x3000 + len(body)] = body
        MEM[r] = bytes(m)
    return problems


def kana(b):
    out = []
    for c in b:
        if c == 0x0D: out.append('\n')
        elif c == 0x0A: pass
        elif 0xA1 <= c <= 0xDF: out.append(chr(0xFF61 + c - 0xA1))
        elif 0x20 <= c < 0x7F: out.append(chr(c))
        else: out.append('?')
    return ''.join(out)


def vocabulary():
    """Word list in SARADAP0: entries [id][word]\\0, verbs first, then nouns (ids restart)."""
    d = FILES['SARADAP0']
    i = d.find(b'RIGHT') - 1
    verbs, nouns = {}, {}
    cur = verbs
    last = -1
    while i < len(d):
        idb = d[i]
        e = d.find(b'\0', i + 1)
        w = d[i + 1:e]
        if not w or e - i > 20:
            break
        if cur is verbs and idb != 0xFF and last >= 0 and idb + 10 < last:
            cur = nouns
        if idb != 0xFF:
            last = idb
        if any(0xA1 <= c <= 0xDF for c in w) and all(0xA1 <= c <= 0xDF or 0x30 <= c <= 0x39 for c in w):
            cur.setdefault(idb, []).append(kana(w))
        i = e + 1
    return verbs, nouns


TITLE_TABLES = {'B': (0x502c, 0x5090, 0, 50), 'A': (0x3654, 0x36b2, 107, 47),
                'C': (0x36b1, 0x36e7, 50, 27), 'D': (0x3664, 0x369e, 77, 30)}


def titles():
    """scene -> (arrival text, look-around text)"""
    out = {}
    for r, (t1, t2, first, n) in TITLE_TABLES.items():
        m = MEM[r]
        for i in range(n):
            s = []
            for tb in (t1, t2):
                p = struct.unpack_from('<H', m, tb + 2 * i)[0]
                e = m.find(b'\0', p)
                s.append(kana(m[p:e]))
            out[first + i] = s
    return out


PIC_TABLES = {'B': (0x4fc7, 0, 50), 'C': (0x3645, 50, 27), 'D': (0x35ee, 77, 30), 'A': (0x4b00, 107, 47)}


def picture(sid):
    """vector picture data of a scene (original format, terminator included)"""
    for r, (tb, first, n) in PIC_TABLES.items():
        if first <= sid < first + n:
            m = MEM[r]
            a = struct.unpack_from('<H', m, tb + 2 * (sid - first))[0]
            p = a
            while True:
                c = m[p]
                t = c & 0xC0
                if t == 0:
                    return bytes(m[a:p + 1])
                p += 4 if t == 0xC0 else 3
    raise KeyError(sid)


def initial_flags():
    """New-game state: the region files set a few flags (starting items) from a (value, address) table."""
    import re
    m = MEM['B']
    i = m.find(b'\xbb\x00\x01\xba\x01\x01\xb9\xff\x00', 0x3000)
    m2 = re.search(rb'\xbb(..)\x8a\x07\x0a\xc0', m[i:i + 40], re.S)
    t = int.from_bytes(m2.group(1), 'little')
    flags = bytearray(256)
    while m[t]:
        a = int.from_bytes(m[t + 1:t + 3], 'little')
        if 0x100 <= a < 0x200: flags[a - 0x100] = m[t]
        t += 3
    return bytes(flags)


def ask2_prompt():
    """Prompt the original prints when a command needs a second noun ("what with?")."""
    m = MEM['B']
    i = m.find(bytes([0xa0, 0x5c, 0x02, 0xfe, 0xc0, 0x74, 0x03, 0xfe, 0xc8, 0xc3]), 0x3000) + 13
    return kana(m[i:m.find(b'\0', i)])
