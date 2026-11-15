"""Scene records -> rule/op structures (engine independent)."""
import json
import sym, source
CFG = {'A': (0x35f6, 0x6b), 'B': (0x35fe, 0), 'C': (0x367b, 0x32), 'D': (0x362a, 0x4d)}
VALID = {'A': range(107, 154), 'B': range(0, 50), 'C': range(50, 77), 'D': range(77, 107)}
import struct


def build_records(r):
    tb, first = CFG[r]
    reg = sym.Region(r, tb, first)
    first_ptr = reg.b(tb) | reg.b(tb + 1) << 8
    n = (first_ptr - tb) // 2
    w = [reg.b(tb + 2 * i) | reg.b(tb + 2 * i + 1) << 8 for i in range(n)]
    recs = []
    for i, p in enumerate(w):
        later = [x for x in w if x > p]
        e = min(later) if later else p + 300
        rr = reg.slice(p, e)
        hdr = list(rr[:13]); j = 13; l1 = []
        while j < len(rr) and rr[j] != 0xff:
            l1.append(tuple(rr[j:j + 3])); j += 3
        j += 1; l2 = []
        while j + 3 < len(rr) and rr[j] != 0xff:
            l2.append((rr[j], rr[j + 1], rr[j + 2] | rr[j + 3] << 8)); j += 4
        recs.append(dict(id=first + i, ptr=p, hdr=hdr, l1=l1, l2=l2))
    return recs


S = {}
NOUN, NOUN2 = 0x25b, 0x25c


def strip_fail(t):
    return t == [('fail',)] or t == []


def specialise(tree, noun):
    """noun = int (known) or None (none of the tested ones)."""
    out = []
    for op in tree:
        if op[0] == 'if':
            _, a, v, t, e = op
            if a == NOUN:
                if noun == v: out += specialise(t, noun)
                else: out += specialise(e, noun)
                return out
            out.append(('if', a, v, specialise(t, noun), specialise(e, noun)))
            return out
        if op[0] == 'iflt':
            out.append(('iflt', op[1], op[2], specialise(op[3], noun), specialise(op[4], noun)))
            return out
        out.append(op)
    return out


def simplify(tree):
    """merge consecutive text, drop empty ifs."""
    out = []
    for op in tree:
        if op[0] == 'if':
            t = simplify(op[3]); e = simplify(op[4])
            if t == e:
                out += t; continue
            out.append(('if', op[1], op[2], t, e))
        elif op[0] == 'iflt':
            t = simplify(op[3]); e = simplify(op[4])
            if t == e:
                out += t; continue
            out.append(('iflt', op[1], op[2], t, e))
        elif op[0] == 'text' and out and out[-1][0] == 'text':
            out[-1] = ('text', out[-1][1] + op[1], 0)
        else:
            out.append(op)
    return out


def rules_for(tree, verb, nonoun=False):
    """returns list of (verb, noun|None|'other', ops)"""
    if nonoun:
        t = simplify(specialise(tree, None))
        return [] if strip_fail(t) else [(verb, 0xff, t)]
    ns = set(); sym.collect_nouns(tree, ns)
    res = []
    for n in sorted(ns):
        t = simplify(specialise(tree, n))
        if not strip_fail(t): res.append((verb, n, t))
    t = simplify(specialise(tree, None))
    if not strip_fail(t): res.append((verb, 'other', t))
    return res


def convert_region(r):
    tb, first = CFG[r]
    reg = sym.Region(r, tb, first)
    rooms = {}
    gl = {}
    # global item examine table
    import re, struct
    seg = source.MEM[r]
    m = re.search(rb'\xbe(..)\x8a\x2c\xfe\xc5\x75\x03\xe9..\xfe\xcd\x3a\xc5\x74', seg, re.S)
    ga = struct.unpack('<H', m.group(1))[0]
    glob = []
    i = ga
    while seg[i] != 0xff:
        glob.append((seg[i], seg[i + 1] | seg[i + 2] << 8, seg[i + 3] | seg[i + 4] << 8)); i += 5
    mm = re.search(rb'\x8a\x05\xfe\xc0\x74(.)\xfe\xc8\xa2\x01\x01\xe9', bytes(seg[0x3000:0x3500]), re.S)
    useexit = 0x3000 + mm.start(); cantgo = useexit + 6 + mm.group(1)[0]
    for d in S[r]:
        sid = d['id']
        if sid not in VALID[r]: continue
        e = sym.Exec(reg)
        room = dict(id=sid, hdr=d['hdr'], rules=[], errors=[])
        hdr = d['hdr']
        # directions
        for v in (0, 2, 4, 6):
            ext = hdr[9 + (v >> 1)]
            custom = hdr[0] != 0
            ptr = hdr[(v | 1)] | hdr[(v | 1) + 1] << 8
            if custom and ptr == cantgo:
                continue                      # "ｿﾉ ﾎｳｺｳﾍﾊ ｲｹﾏｾﾝ" -> direction not offered
            if custom and ptr == useexit:
                if ext != 0xff: room['rules'].append((v, 0xff, [('goto', ext)]))
                continue
            if custom and not (0x3000 <= ptr < 0x3500):
                try:
                    t = e.run(ptr, {}, {})
                    room['rules'].append((v, 0xff, simplify(t)))
                except sym.Abort as ex:
                    room['errors'].append(('dir', v, str(ex)))
                    if ext != 0xff: room['rules'].append((v, 0xff, [('goto', ext)]))
            elif ext != 0xff:
                room['rules'].append((v, 0xff, [('goto', ext)]))
        # look
        done = set()
        for ent in d['l1']:
            if len(ent) != 3: continue
            noun, lo, hi = ent
            try:
                t = e.run(lo | hi << 8, {}, {'al': sym.Sym(NOUN), 'ch': sym.Sym(NOUN)})
                tt = simplify(t)
                if not strip_fail(tt): room['rules'].append((9, noun, tt)); done.add(noun)
            except sym.Abort as ex:
                room['errors'].append(('look', noun, str(ex)))
        for noun, item, ptr in glob:
            if noun in done: continue
            try:
                t = simplify(e.run(ptr, {}, {'al': sym.Sym(NOUN)}))
                room['rules'].append((9, noun, t, item))
            except sym.Abort as ex:
                room['errors'].append(('gl', noun, str(ex)))
        # other verbs
        seen = set()
        for verb, fl, ptr in d['l2']:
            if verb in seen or verb in (8, 9, 0x13, 0x14, 0x23, 0x24) or verb < 8: continue
            seen.add(verb)
            try:
                if fl == 0:
                    t = e.run(ptr, {}, {'al': 0xff, 'ch': 0xff})
                    room['rules'] += rules_for(t, verb, nonoun=True)
                else:
                    t = e.run(ptr, {}, {'al': sym.Sym(NOUN), 'ch': sym.Sym(NOUN)})
                    room['rules'] += rules_for(t, verb)
            except sym.Abort as ex:
                room['errors'].append(('verb', verb, str(ex)))
        rooms[sid] = room
    return rooms, glob


def convert_all(log=print):
    S.clear()
    for r in 'ABCD':
        S[r] = build_records(r)
    allr = {}
    for r in 'ABCD':
        rooms, g = convert_region(r)
        allr.update(rooms)
    # manual patches for handlers the symbolic executor cannot follow
    A = source.MEM['A']
    def txt(a):
        return sym.kana(A[a:A.find(b'\0', a)])
    r130 = allr[130]
    r130['rules'] = [x for x in r130['rules'] if x[0] != 15]
    r130['rules'].append((15, 0xff, [('if', 0x131, 0, [('text', txt(0x3df9) + '\n', 0), ('set', 0x131, 1), ('end',)],
                                                   [('text', txt(0x3ddc) + '\n', 0), ('set', 0x131, 0), ('end',)])]))
    r130['errors'] = []
    r151 = allr[151]
    for v in (0, 2, 4, 6):
        r151['rules'].append((v, 0xff, [('text', txt(0x439c) + '\n', 0), ('end',)]))
    r151['errors'] = []
    nerr = sum(len(x['errors']) for x in allr.values())
    nr = sum(len(x['rules']) for x in allr.values())
    log('%d rooms, %d rules, %d unresolved handlers' % (len(allr), nr, nerr))
    # normalise (tuples -> lists, str keys) exactly like a JSON round trip
    return json.loads(json.dumps({str(k): v for k, v in allr.items()}, ensure_ascii=False))
