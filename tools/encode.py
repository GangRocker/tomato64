"""Converted scenario -> engine data (global asm tables) + per-room data blobs."""
import re
from gamedata import kb, hexline
import source

BASE = 0x3402
V_GO, V_ITEMS = 0xF0, 19
SKIP_VERBS = {8, 19, 20, 35, 36}


def clean(n):
    return n and all(0xFF61 <= ord(c) <= 0xFF9F or 0x20 <= ord(c) < 0x7F for c in n) and not re.search(r'[A-Z]{3}', n)


def load_vocab():
    vv, nn = source.vocabulary()
    verbs = {}; nouns = {}
    for k, names in vv.items():
        c = [n for n in names if clean(n)]
        if c: verbs[int(k)] = c[0]
    for k, names in nn.items():
        c = [n for n in names if clean(n)]
        if c: nouns[int(k)] = c[0]
    verbs[0] = 'ﾐｷﾞ'; verbs[2] = 'ﾋﾀﾞﾘ'; verbs[4] = 'ﾏｴ'; verbs[6] = 'ｳｼﾛ'
    verbs[9] = 'ﾐﾙ'; verbs[34] = 'ﾊｼﾞﾒﾙ'; verbs[30] = 'ｵﾘﾙ'
    nouns[10] = 'ﾐｽﾞ'
    nouns[N_AROUND] = 'ﾏﾜﾘ'
    NOUNS.update(nouns)
    return verbs, nouns


# noun -> (flag address, value meaning "hint heard", derived engine flag)
# G13: the password told in scene 38; CYAN: the button colour told in scene 65
KNOWN_ANSWERS = {58: (0x119, 3, 0xF3), 80: (0x122, 5, 0xF4)}


def fmap(a):
    if 0x100 <= a < 0x1F0: return a - 0x100
    return {0x25c: 0xF0, 0x25d: 0xF1, 0xFFF0: 0xF2}[a]


class Enc:
    def __init__(self, base):
        self.base = base; self.b = bytearray()

    def here(self): return self.base + len(self.b)


NEEDP = set()
NOUNS = {}
CUR = {'room': None}


def enc_ops(ops, st=None):
    if st is None: st = {'last': None}
    out = bytearray()
    for i, op in enumerate(ops):
        k = op[0]
        if k == 'set' and op[1] == 0x101: st['last'] = op[2]
        if k == 'redraw':
            if st['last'] is not None:
                out += bytes([14, st['last']]); NEEDP.add((CUR['room'], st['last']))
            continue
        if k == 'unk' and op[1] == 'call248':
            out += bytes([5]); continue
        if k == 'unk' and op[1] == 'stub203' and st['last'] is not None:
            out += bytes([4, st['last']]); continue
        if k == 'text':
            if op[1] in POOL:      # repeated text: print it from the room's string pool
                out += bytes([7, POOL[op[1]] & 255, POOL[op[1]] >> 8])
            else:
                out += bytes([1]) + kb(op[1]) + b'\0'
        elif k == 'set': out += bytes([2, fmap(op[1]), op[2] & 255])
        elif k == 'add': out += bytes([10, fmap(op[1]), op[2] & 255])
        elif k == 'toggle': out += bytes([11, fmap(op[1])])
        elif k == 'goto': out += bytes([4, op[1]])
        elif k == 'end': out += bytes([0])
        elif k == 'fail': out += bytes([13])
        elif k in ('choose', 'ask2'):
            addr = 0xFFF0 if k == 'choose' else 0x25C
            vals = []
            branch = {}
            def coll(o):
                for q in o:
                    if q[0] == 'if':
                        if q[1] == addr and q[2] not in vals:
                            vals.append(q[2]); branch[q[2]] = repr(q[3])
                        coll(q[3]); coll(q[4])
            coll(ops[i + 1:])
            invn = set(n for n, _ in INV)
            # an answer that does exactly what an inventory item's answer does is only a synonym of that
            # item (e.g. BIN for the canteen at the pond): the item itself is offered from the inventory
            invb = set(branch[v] for v in vals if v in invn)
            cand = [v for v in vals if v not in invn and v in NOUNS and branch[v] not in invb]
            # answers the player only learns from a hint elsewhere: offer them once that hint was heard
            pre = b''
            vis = {}
            for n, (fa, fv, dflag) in KNOWN_ANSWERS.items():
                if n in cand:
                    pre += bytes([2, dflag, 0, 3, fmap(fa), fv, 3, 0, 2, dflag, 1])
                    vis[n] = dflag
            if k == 'ask2':        # the original asks "ﾅﾆｦ ﾂｶｯﾃ" for the second noun
                pre = bytes([1]) + kb(source.ask2_prompt()) + b'\0' + pre
            out += pre + bytes([12, fmap(addr)]) + b''.join(bytes([v, vis.get(v, 0xFF)]) for v in cand) + b'\xff'

        elif k == 'iflt':        # then-block when flag < v (unsigned), else-block otherwise
            _, a, v, t, e = op
            tb = enc_ops(t, dict(st)); eb = enc_ops(e, dict(st))
            term = bool(t) and t[-1][0] in ('end', 'goto', 'fail')
            if not term and eb:
                tb += bytes([9, len(eb) & 255, len(eb) >> 8])
            out += bytes([6, fmap(a), v & 255, len(tb) & 255, len(tb) >> 8]) + tb + eb
        elif k == 'if':
            _, a, v, t, e = op
            tb = enc_ops(t, dict(st)); eb = enc_ops(e, dict(st))
            term = bool(t) and t[-1][0] in ('end', 'goto', 'fail')
            if not term and eb:
                tb += bytes([9, len(eb) & 255, len(eb) >> 8])
            out += bytes([3, fmap(a), v & 255, len(tb) & 255, len(tb) >> 8]) + tb + eb
        else:
            pass  # redraw / unk
    return bytes(out)


def ends(ops):
    return bytes([0])


TITLES = {}
N_AROUND = 0xEF


POOL = {}


def use_rewrite(ops):
    """The original parser accepted "X ｦ Y ﾃﾞ <verb>": [0x25d] == 3 when a tool word was typed, else it answers
    "ﾅﾆｦ ﾂｶｯﾃ" + fail.  With menus there is no typed tool, so ask for it (like the pond's "ﾅﾆｦ ﾂｶｯﾃ" prompt)."""
    out = []
    for op in ops:
        if op[0] == 'if' and op[1] == 0x25D and op[2] == 3 and any(o[0] == 'text' and 'ﾂｶｯﾃ' in o[1] for o in op[4]):
            out += [('ask2',)] + use_rewrite(op[3])
            return out
        if op[0] in ('if', 'iflt'):
            op = (op[0], op[1], op[2], use_rewrite(op[3]), use_rewrite(op[4]))
        out.append(op)
    return out


def held_flag(ops):
    """A rule that starts with "if <flag> == 0: <system message>; end" refuses because the item is not held
    (the original prints such refusals through its system-message routine, stub $23C).
    Returns the flag index so the noun is only offered while the item is held, else $FF."""
    if ops and ops[0][0] == 'if' and ops[0][2] == 0 and 0x100 <= ops[0][1] < 0x1F0:
        th = ops[0][3]
        texts = [o for o in th if o[0] == 'text']
        if len(texts) == 1 and len(texts[0]) > 2 and (texts[0][2] == 0x23C or 'ﾓｯﾃ' in texts[0][1]) and all(o[0] in ('text', 'end') for o in th):
            return ops[0][1] - 0x100
    return 0xFF


def build_room(room, sid, verbs, nouns):
    """returns bytes of room blob (base BASE)"""
    rules = list(room['rules'])
    CUR['room'] = sid
    if not TITLES: TITLES.update({str(k): v for k, v in source.titles().items()})
    tt = TITLES.get(str(sid), ['', ''])
    arrive, desc = tt
    if sid == 0: arrive = 'ﾊｼﾞﾒﾙ ｦ ｴﾗﾝﾃﾞ ｸﾀﾞｻｲ｡'
    if desc: rules = [[9, N_AROUND, [['text', desc + '\n'], ['end']]]] + rules
    byverb = {}
    for r in rules:
        v, n, ops = r[0], r[1], use_rewrite(r[2])
        vis = (r[3] - 0x100) if len(r) > 3 else 0xFF
        if vis == 0xFF and isinstance(n, int) and n < 0xF0:
            vis = held_flag(ops)
        nn = 0xFF if n == 255 else (0xFD if n == 'other' else n)
        byverb.setdefault(v, []).append((nn, ops, vis))
    # order rules: specific, then wildcard
    allrules = []
    for v in sorted(byverb):
        lst = byverb[v]
        lst.sort(key=lambda x: (x[0] in (0xFD, 0xFF), ))
        for nn, ops, vis in lst: allrules.append((v, nn, ops, vis))
    # layout: header(6) | verbtab | lists | rules | scripts
    dirs = [d for d in (0, 2, 4, 6) if d in byverb]
    vt = []  # (id, mode, list bytes)
    if dirs: vt.append((V_GO, 3, bytes(dirs) + b'\xff'))
    for v in sorted(byverb, key=lambda x: (x != 9, x)):
        if v in (0, 2, 4, 6) or v in SKIP_VERBS or v not in verbs: continue
        lst = byverb[v]
        specific = []
        for nn, ops, vis in lst:
            if nn < 0xF0 and nn in nouns and nn not in [s for s, _ in specific]: specific.append((nn, vis))
        wild = any(nn == 0xFD for nn, _, _ in lst)
        if not specific: mode = 0          # noun not needed (also when only a catch-all rule exists)
        else: mode = 2 if wild else 1
        lb = b''.join(bytes([n, vis]) for n, vis in specific) + b'\xff'
        vt.append((v, mode, lb))
    off = 6
    vtab_off = off; off += 4 * len(vt) + 1
    list_off = []
    for v, m, lb in vt:
        list_off.append(off); off += len(lb)
    rules_off = off; off += 5 * len(allrules) + 1
    # string pool: texts used more than once in this room are stored once
    cnt = {}
    def walk(ops):
        for o in ops:
            if o[0] == 'text': cnt[o[1]] = cnt.get(o[1], 0) + 1
            elif o[0] in ('if', 'iflt'): walk(o[3]); walk(o[4])
    for v, nn, ops, vis in allrules: walk(ops)
    POOL.clear()
    pool = b''
    for t, c in sorted(cnt.items()):
        kt = kb(t)
        if c > 1 and len(kt) >= 3:
            POOL[t] = BASE + off + len(pool)
            pool += kt + b'\0'
    off += len(pool)
    scripts = []
    script_off = []
    for v, nn, ops, vis in allrules:
        sb = enc_ops(ops) + b'\0'
        script_off.append(off); scripts.append(sb); off += len(sb)
    entry = b''
    if arrive:
        entry = bytes([1]) + kb(arrive + '\n') + b'\0\0'
    entry_off = off; off += len(entry)
    b = bytearray()
    b += (BASE + vtab_off).to_bytes(2, 'little') + (BASE + rules_off).to_bytes(2, 'little')
    b += ((BASE + entry_off).to_bytes(2, 'little') if entry else b'\0\0')
    for (v, m, lb), lo in zip(vt, list_off):
        b += bytes([v, m]) + (BASE + lo).to_bytes(2, 'little')
    b += b'\xff'
    for v, m, lb in vt: b += lb
    for (v, nn, ops, vis), so in zip(allrules, script_off):
        b += bytes([v, nn, vis]) + (BASE + so).to_bytes(2, 'little')
    b += b'\xff'
    b += pool
    for sb in scripts: b += sb
    b += entry
    assert len(b) == off
    return bytes(b)


def global_asm(verbs, nouns, inv, roomdisk):
    out = []
    def lab(name, s):
        out.append(name + ':\n' + hexline(kb(s) + b'\0'))
    lab('name_back', 'ﾓﾄﾞﾙ'); lab('msg_nothing', 'ﾅﾆﾓ ｵｺﾘﾏｾﾝ｡'); lab('msg_fail', 'ﾃﾞｷﾏｾﾝ｡')
    lab('msg_disk1', 'ﾃﾞｨｽｸ'); lab('msg_disk2', ' ｦ ｲﾚﾃ ﾘﾀｰﾝ')
    lab('msg_t1', 'ｻﾗﾀﾞﾉ ｸﾆﾉ ﾄﾏﾄﾋﾒ'); lab('msg_t2', 'C64 ﾆﾎﾝｺﾞ ｲｼｮｸﾊﾞﾝ'); lab('msg_t3', 'ﾎﾞﾀﾝ ｶ ｽﾍﾟｰｽ ﾃﾞ ｽﾀｰﾄ'); lab('msg_t4', 'FONT: MISAKI GOTHIC (C) NUM KADOMA')
    lab('msg_items', 'ﾓﾁﾓﾉ: '); lab('msg_noitems', 'ﾅﾆﾓ ﾓｯﾃｲﾏｾﾝ｡'); lab('vname_items', 'ﾓﾁﾓﾉ'); lab('vname_go', 'ｲﾄﾞｳ')
    lab('vname_sys', 'ｼｽﾃﾑ'); lab('vname_save', 'ｾｰﾌﾞ'); lab('vname_load', 'ﾛｰﾄﾞ'); lab('vname_restart', 'ﾊｼﾞﾒｶﾗ'); lab('vname_vol', 'ｵﾝﾘｮｳ'); lab('vname_v0', 'ｵﾌ')
    for i in range(1, 6): lab('vname_v%d' % i, str(i))
    lab('msg_savdisk', 'ｾｰﾌﾞﾖｳ ﾉ ﾃﾞｨｽｸ ｦ ｲﾚﾃ ﾘﾀｰﾝ\n(ﾄﾘｹｼ: X ｷｰ)')
    lab('msg_saved', 'ｾｰﾌﾞ ｼﾏｼﾀ｡'); lab('msg_saverr', 'ｾｰﾌﾞ ﾃﾞｷﾏｾﾝﾃﾞｼﾀ｡')
    lab('msg_loaded', 'ﾛｰﾄﾞ ｼﾏｼﾀ｡'); lab('msg_loaderr', 'ﾛｰﾄﾞ ﾃﾞｷﾏｾﾝﾃﾞｼﾀ｡')
    vn = dict(verbs); vn[V_GO] = None
    for v, n in verbs.items():
        if v not in (0, 2, 4, 6): lab('vn_%02x' % v, n)
    for d in (0, 2, 4, 6): lab('dn_%d' % d, verbs[d])
    for n, name in nouns.items(): lab('nn_%02x' % n, name)
    lo = []; hi = []
    for i in range(0xF1):
        l = 'vname_go' if i == V_GO else ('vn_%02x' % i if i in verbs and i not in (0, 2, 4, 6) else 'name_back')
        lo.append('<' + l); hi.append('>' + l)
    out.append('vname_lo: .byte ' + ','.join(lo) + '\nvname_hi: .byte ' + ','.join(hi) + '\n')
    lo = []; hi = []
    for i in range(8):
        l = 'dn_%d' % i if i in (0, 2, 4, 6) else 'name_back'
        lo.append('<' + l); hi.append('>' + l)
    out.append('dname_lo: .byte ' + ','.join(lo) + '\ndname_hi: .byte ' + ','.join(hi) + '\n')
    lo = []; hi = []
    for i in range(0xF0):
        l = 'nn_%02x' % i if i in nouns else 'name_back'
        lo.append('<' + l); hi.append('>' + l)
    out.append('noun_lo: .byte ' + ','.join(lo) + '\nnoun_hi: .byte ' + ','.join(hi) + '\n')
    out.append('invtab:\n')
    for nid, f in inv: out.append(hexline(bytes([nid, f])))
    out.append('        .byte $ff\n')
    fi = source.initial_flags()
    out.append('flaginit:\n' + ''.join(hexline(fi[i:i + 16]) for i in range(0, 256, 16)))
    out.append('roomdisk: .byte ' + ','.join(str(x) for x in roomdisk) + '\n')
    return ''.join(out)


INV = [(2, 2), (57, 3), (49, 4), (59, 5), (60, 6), (13, 10), (19, 11), (18, 12), (17, 13), (20, 14), (21, 15), (23, 16), (76, 17), (77, 18), (78, 19), (27, 20), (28, 21), (62, 23),
       (67, 30), (68, 31), (81, 36), (1, 37), (42, 45), (86, 39), (104, 51)]
