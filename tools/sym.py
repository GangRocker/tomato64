"""Symbolic executor for the 8086 scene handlers of Tomato-hime.
Runs handler code, hooks runtime stubs, forks on flag/noun tests and returns an op tree.
Ops: ('text',s) ('set',addr,val) ('goto',scene) ('end',) ('fail',) ('unk',what)
     ('if',addr,val,then,else)   meaning if mem[addr]==val then ... else ...
"""
import re, struct
import source


class Sym:
    def __init__(self, addr, off=0):
        self.addr = addr; self.off = off

    def __repr__(self):
        return 'M[%x]%+d' % (self.addr, self.off)


CHOICE = 0xfff0


class NotSym:
    def __init__(self, addr): self.addr = addr


class Abort(Exception):
    pass


def kana(b):
    out = []
    for c in b:
        if c == 0x0d: out.append('\n')
        elif c == 0x0a: pass
        elif 0xa1 <= c <= 0xdf: out.append(chr(0xff61 + c - 0xa1))
        elif 0x20 <= c < 0x7f: out.append(chr(c))
        else: out.append('?')
    return ''.join(out)


class Region:
    def __init__(self, name, table_base, first_id):
        self.name = name; self.tb = table_base; self.first = first_id
        self.mem = source.MEM[name]
        self.find_specials()

    def b(self, a):
        return self.mem[a & 0xffff]

    def slice(self, a, e):
        return bytes(self.mem[a:e])

    def find_specials(self):
        M = self.mem
        # main loop: bc 00 01 bb lo hi a0 01 01
        seg = M[0x2f00:0x3800]
        i = seg.find(bytes([0xbc, 0x00, 0x01, 0xbb]))
        while i >= 0 and seg[i + 6] != 0xa0:
            i = seg.find(bytes([0xbc, 0x00, 0x01, 0xbb]), i + 1)
        self.loop = 0x2f00 + i
        # goto: a2 01 01 e9
        i = seg.find(bytes([0xa2, 0x01, 0x01, 0xe9]))
        self.goto = 0x2f00 + i
        # restart = target of that jmp
        rel = struct.unpack_from('<h', seg, i + 4)[0]
        self.restart = (0x2f00 + i + 3 + 3 + rel) & 0xffff
        # fail: first E8 before 'mov bx,[0x260]' (8b 1e 60 02)
        j = seg.find(bytes([0x8b, 0x1e, 0x60, 0x02]))
        k = j
        while seg[k] != 0xe8 or seg[k + 3 + 0] == 0: k -= 1
        # walk back to the e8 that precedes the text
        k = j - 1
        while seg[k] != 0x00: k -= 1  # end of text
        t = k - 1
        while seg[t] >= 0x20 and not (seg[t - 3] == 0xe8 and seg[t - 3 + 3 - 3] == 0xe8 and False): t -= 1
        # simpler: search backwards for e8 with target in stub range
        t = k
        while True:
            if seg[t] == 0xe8:
                rel = struct.unpack_from('<h', seg, t + 1)[0]
                tg = (0x2f00 + t + 3 + rel) & 0xffff
                if 0x230 <= tg <= 0x260: break
            t -= 1
        self.fail = 0x2f00 + t
        # reconcile: fail routine begins at first e8 of consecutive text print chain; use label found
        self.print_stub = tg
        self.redraw = set()
        for mm in re.finditer(re.escape(bytes([0xa0, 0x01, 0x01, 0x2c])), bytes(M[0:0x4a00])):
            if mm.start() > 0x3400: self.redraw.add(mm.start())
        # 351c-like item prompt: mov bx,0x280 ; call 0x230 ; call 0x24e
        m = bytes(M[0x3000:0x4a00]).find(bytes([0xbb, 0x80, 0x02, 0xe8]))
        self.ask_item = 0x3000 + m if m >= 0 else -1
        m = bytes(M[0x3000:0x4a00]).find(bytes([0xa0, 0x5c, 0x02, 0xfe, 0xc0, 0x74, 0x03, 0xfe, 0xc8, 0xc3]))
        self.ask2 = 0x3000 + m if m >= 0 else -1


def stub_kind(a):
    return a


class Exec:
    MAXPATH = 4000

    def __init__(self, reg):
        self.reg = reg
        self.count = 0
        self.unk = set()

    def run(self, start, mem, regs, cs=None, depth=0, flags=None):
        """Returns op tree (list)."""
        reg = self.reg
        mem = dict(mem); regs = dict(regs); cs = list(cs or [])
        ops = []
        ip = start
        zf = False; cf = False
        zsym = None  # ('eq', Sym, imm) pending symbolic zero flag
        if flags: zf, cf, zsym = flags
        steps = 0
        while True:
            steps += 1
            if steps > 3000: raise Abort('loop')
            self.count += 1
            if self.count > 200000: raise Abort('budget')
            # specials
            if ip == reg.loop:
                ops.append(('end',)); return ops
            if ip == reg.fail or ip == reg.fail + 0:
                ops.append(('fail',)); return ops
            if ip == reg.goto:
                al = regs.get('al')
                if isinstance(al, Sym): raise Abort('goto sym')
                ops.append(('goto', al)); return ops
            if ip == reg.restart:
                ops.append(('end',)); return ops
            if ip < 0x400 and ip >= 0x200:
                # runtime stub call reached via jmp (tail) -> treat as unknown
                ops.append(('unk', 'stub%x' % ip)); return ops
            b = reg.b
            op = b(ip)

            def rd16(a): return b(a) | b(a + 1) << 8

            def getr8(n):
                if n in regs: return regs[n]
                raise Abort('reg ' + n)

            r8 = ['al', 'cl', 'dl', 'bl', 'ah', 'ch', 'dh', 'bh']
            r16 = ['ax', 'cx', 'dx', 'bx', 'sp', 'bp', 'si', 'di']

            def g8(n):
                if n in regs: return regs[n]
                return 0

            def s8(n, v): regs[n] = v

            def g16(n):
                if n in regs and not isinstance(regs[n], Sym): return regs[n]
                lo = n[0] + 'l'; hi = n[0] + 'h'
                if n in ('si', 'di', 'bp', 'sp'): return regs.get(n, 0)
                return (regs.get(hi, 0) & 0xff) << 8 | (regs.get(lo, 0) & 0xff)

            def s16(n, v):
                if n in ('si', 'di', 'bp', 'sp'): regs[n] = v; return
                regs[n[0] + 'l'] = v & 0xff; regs[n[0] + 'h'] = (v >> 8) & 0xff

            def memget(a):
                if a in mem: return mem[a]
                return Sym(a, 0)

            def setzf_val(v):
                nonlocal zf, zsym
                if isinstance(v, Sym):
                    zsym = ('eq', v, 0); zf = None
                else:
                    zf = (v & 0xff) == 0; zsym = None

            def modrm_mem():
                nonlocal ip
                m = b(ip + 1)
                mod = m >> 6; rm = m & 7; rg = (m >> 3) & 7
                if mod == 3: return ('reg', rg, rm), 2
                if mod == 0 and rm == 6:
                    return ('abs', rg, rd16(ip + 2)), 4
                if mod == 0 and rm == 7:  # [bx]
                    return ('bx', rg, 0), 2
                raise Abort('modrm %02x at %x' % (m, ip))

            if op == 0xf9: cf = True; ip += 1; continue
            if op == 0xf8: cf = False; ip += 1; continue
            if op == 0x90 or op == 0x9f or op == 0x9e or op == 0xfc or op == 0xfa or op == 0xfb:
                ip += 1; continue
            if 0xb0 <= op <= 0xb7:
                s8(r8[op - 0xb0], b(ip + 1)); ip += 2; continue
            if 0xb8 <= op <= 0xbf:
                s16(r16[op - 0xb8], rd16(ip + 1)); ip += 3; continue
            if op == 0xa0:
                regs['al'] = memget(rd16(ip + 1)); ip += 3; continue
            if op == 0xa2:
                v = regs.get('al', 0)
                a = rd16(ip + 1)
                if isinstance(v, NotSym):
                    if v.addr != a: raise Abort('notsym store')
                    ops.append(('toggle', a)); mem.pop(a, None); regs['al'] = Sym(a, 0); ip += 3; continue
                if isinstance(v, Sym):
                    if v.addr == a and v.off:
                        ops.append(('add', a, v.off)); mem.pop(a, None); ip += 3; continue
                    if v.addr == a: ip += 3; continue
                    ops.append(('copy', a, v.addr, v.off)); mem.pop(a, None); ip += 3; continue
                mem[a] = v; ops.append(('set', a, v)); ip += 3; continue
            if op in (0x88, 0x8a):
                (kind, rg, x), ln = modrm_mem()
                if kind == 'reg':
                    rn = r8[rg]; rm = r8[x]
                    if op == 0x8a: regs[rn] = g8(rm)
                    else: regs[rm] = g8(rn)
                elif kind == 'abs':
                    rn = r8[rg]
                    if op == 0x8a: regs[rn] = memget(x)
                    else:
                        v = g8(rn)
                        if isinstance(v, Sym): raise Abort('store sym')
                        mem[x] = v; ops.append(('set', x, v))
                elif kind == 'bx':
                    rn = r8[rg]; a = g16('bx')
                    if op == 0x8a: regs[rn] = memget(a)
                    else:
                        v = g8(rn)
                        if isinstance(v, Sym): raise Abort('store sym')
                        mem[a] = v; ops.append(('set', a, v))
                ip += ln; continue
            if op == 0xc6:
                (kind, rg, x), ln = modrm_mem()
                if kind == 'abs':
                    v = b(ip + 4); mem[x] = v; ops.append(('set', x, v)); ip += 5; continue
                if kind == 'bx':
                    v = b(ip + 2); a = g16('bx'); mem[a] = v; ops.append(('set', a, v)); ip += 3; continue
                raise Abort('c6')
            if op == 0x8b and b(ip + 1) == 0x1e and rd16(ip + 2) in (0x25e, 0x260, 0x262, 0x264):
                ops.append(('fail',)); return ops
            if op in (0x8b, 0x89):
                (kind, rg, x), ln = modrm_mem()
                if kind == 'reg':
                    if op == 0x8b: s16(r16[rg], g16(r16[x]))
                    else: s16(r16[x], g16(r16[rg]))
                    ip += ln; continue
                raise Abort('mov16 %02x%02x at %x' % (op, b(ip + 1), ip))
            if op == 0xf6 and b(ip + 1) == 0xd0:
                v = regs.get('al', 0)
                if isinstance(v, Sym) and v.off == 0: regs['al'] = NotSym(v.addr)
                elif isinstance(v, Sym): raise Abort('not off')
                else: regs['al'] = (~v) & 0xff
                ip += 2; continue
            if op == 0x2c:
                imm = b(ip + 1); v = regs.get('al', 0)
                if isinstance(v, Sym):
                    nv = Sym(v.addr, v.off - imm); regs['al'] = nv; zsym = ('eq', nv, 0); zf = None; cf = None
                else:
                    nv = (v - imm) & 0xff; cf = (v & 0xff) < imm; regs['al'] = nv; zf = nv == 0; zsym = None
                ip += 2; continue
            if op == 0x3c:
                imm = b(ip + 1); v = regs.get('al', 0)
                if isinstance(v, Sym):
                    zsym = ('eq', v, imm); zf = None; cf = None
                else:
                    zf = (v & 0xff) == imm; cf = (v & 0xff) < imm; zsym = None
                    self._cmp = (v & 0xff, imm)
                ip += 2; continue
            if op == 0x80:
                m = b(ip + 1)
                if m == 0x3e:  # cmp byte [abs],imm
                    a = rd16(ip + 2); imm = b(ip + 4); v = memget(a)
                    if isinstance(v, Sym): zsym = ('eq', v, imm); zf = None; cf = None
                    else: zf = v == imm; cf = v < imm; zsym = None
                    ip += 5; continue
                if m & 0xf8 == 0xc8:  # or r8,imm
                    rn = r8[m & 7]; regs[rn] = g8(rn) | b(ip + 2); ip += 3
                    zf = False; zsym = None; continue
                if m & 0xf8 == 0xe0:  # and r8,imm
                    rn = r8[m & 7]; regs[rn] = g8(rn) & b(ip + 2); ip += 3
                    zf = regs[rn] == 0; zsym = None; continue
                raise Abort('80 %02x' % m)
            if op in (0x0a, 0x22) and b(ip + 1) >> 6 == 3:
                m = b(ip + 1)
                rg = (m >> 3) & 7; rm = m & 7
                if rg == rm:
                    v = g8(r8[rg]); setzf_val(v); cf = False; ip += 2; continue
                x = g8(r8[rg]); y = g8(r8[rm])
                if isinstance(x, Sym) or isinstance(y, Sym): raise Abort('or sym')
                regs[r8[rg]] = (x | y) if op == 0x0a else (x & y); setzf_val(regs[r8[rg]]); ip += 2; continue
            if op in (0x30, 0x32) and b(ip + 1) >> 6 == 3:
                m = b(ip + 1); rg = (m >> 3) & 7; rm = m & 7
                if rg == rm: regs[r8[rg]] = 0; zf = True; zsym = None; ip += 2; continue
                raise Abort('xor')
            if op == 0x3a and b(ip + 1) >> 6 == 3:
                m = b(ip + 1); rg = (m >> 3) & 7; rm = m & 7
                x = g8(r8[rg]); y = g8(r8[rm])
                if isinstance(x, Sym) and not isinstance(y, Sym):
                    zsym = ('eq', x, y); zf = None; cf = None
                elif isinstance(y, Sym) or isinstance(x, Sym): raise Abort('cmp rr sym')
                else: zf = x == y; cf = x < y; zsym = None
                ip += 2; continue
            if op == 0xfe:
                m = b(ip + 1)
                if m >> 6 == 3:
                    rn = r8[m & 7]; v = g8(rn)
                    dec = (m >> 3) & 7
                    if isinstance(v, Sym):
                        nv = Sym(v.addr, v.off + (1 if dec == 0 else -1))
                        regs[rn] = nv; zsym = ('eq', nv, 0); zf = None
                    else:
                        nv = (v + (1 if dec == 0 else -1)) & 0xff
                        regs[rn] = nv; zf = nv == 0; zsym = None
                    ip += 2; continue
                if m in (0x06, 0x0e) or m == 0x07 or m == 0x0f:
                    dec = (m >> 3) & 7
                    if m & 7 == 6: a = rd16(ip + 2); ln = 4
                    else: a = g16('bx'); ln = 2
                    v = memget(a)
                    k = 1 if dec == 0 else -1
                    if isinstance(v, Sym):
                        ops.append(('add', a, k)); mem.pop(a, None)
                        zsym = ('eq', Sym(a, k), 0); zf = None
                    else:
                        nv = (v + k) & 0xff
                        mem[a] = nv; ops.append(('set', a, nv)); zf = nv == 0; zsym = None
                    ip += ln; continue
                raise Abort('fe %02x at %x' % (m, ip))
            if op in (0x74, 0x75, 0x72, 0x73, 0x76, 0x77, 0xeb, 0x7b, 0x7a, 0x70, 0x71, 0x78, 0x79):
                rel = b(ip + 1); rel = rel - 256 if rel > 127 else rel
                tgt = ip + 2 + rel
                if op == 0xeb: ip = tgt; continue
                if op in (0x74, 0x75):
                    want = (op == 0x74)  # jump if zf (jz) / not zf
                    if zsym is not None:
                        kind, v, imm = zsym
                        if isinstance(imm, Sym): raise Abort('sym-sym')
                        # condition: v == imm  (v is Sym with offset)
                        addr = v.addr; val = (imm - v.off) & 0xff
                        # fork
                        s1 = dict(mem); s1[addr] = val
                        t_eq = self.run_sub(ip + 2 if not want else tgt, s1, regs, cs, depth)
                        t_ne = self.run_sub(tgt if not want else ip + 2, mem, regs, cs, depth, neq=(addr, val))
                        ops.append(('if', addr, val, t_eq, t_ne)); return ops
                    if zf is None: raise Abort('zf unknown')
                    ip = tgt if (zf == want) else ip + 2; continue
                if op in (0x72, 0x73, 0x76, 0x77) and cf is None:
                    # unsigned compare of a flag with a constant: fork on  flag < k
                    if zsym is None: raise Abort('cf unknown')
                    kind, v, imm = zsym
                    if isinstance(imm, Sym) or v.off != 0: raise Abort('cf sym')
                    k = imm + (1 if op in (0x76, 0x77) else 0)        # jbe/ja: flag <= imm  ==  flag < imm+1
                    lt_jumps = op in (0x72, 0x76)
                    if op in (0x72, 0x73):     # flag < imm: not equal, carry ; flag >= imm: equality still open
                        f_lt = (False, True, None); f_ge = (None, False, zsym)
                    else:                      # flag <= imm: equality still open ; flag > imm: not equal, no carry
                        f_lt = (None, None, zsym); f_ge = (False, False, None)
                    t_lt = self.run_sub(tgt if lt_jumps else ip + 2, dict(mem), regs, cs, depth, flags=f_lt)
                    t_ge = self.run_sub(ip + 2 if lt_jumps else tgt, dict(mem), regs, cs, depth, flags=f_ge)
                    ops.append(('iflt', v.addr, k, t_lt, t_ge)); return ops
                if op == 0x72:  # jc
                    ip = tgt if cf else ip + 2; continue
                if op == 0x73:
                    ip = ip + 2 if cf else tgt; continue
                if op == 0x76:  # jbe
                    ip = tgt if (cf or zf) else ip + 2; continue
                if op == 0x77:
                    ip = ip + 2 if (cf or zf) else tgt; continue
                if op in (0x7b, 0x7a):
                    # parity tricks around add si; treat as not taken for 7b? ambiguous
                    raise Abort('parity')
                raise Abort('jcc %02x' % op)
            if op == 0xe9:
                rel = rd16(ip + 1); rel = rel - 65536 if rel > 32767 else rel
                tg2 = (ip + 3 + rel) & 0xffff
                if tg2 in reg.redraw:
                    ops.append(('redraw',)); ops.append(('end',)); return ops
                ip = tg2; continue
            if op == 0xe8:
                rel = rd16(ip + 1); rel = rel - 65536 if rel > 32767 else rel
                tgt = (ip + 3 + rel) & 0xffff
                if tgt in (0x239, 0x23c, 0x23f):
                    e = ip + 3
                    while b(e) != 0: e += 1
                    txt = kana(reg.slice(ip + 3, e))
                    if tgt != 0x239: txt += '\n'
                    ops.append(('text', txt, tgt))
                    if tgt == 0x23f:
                        if cs and not isinstance(cs[-1], tuple): ip = cs.pop(); continue
                        ops.append(('end',)); return ops
                    ip = e + 1; continue
                if tgt == 0x245:
                    ops.append(('text', '\n', tgt)); ip += 3; continue
                if tgt == 0x230 and b(ip + 3) == 0xe8 and ((ip + 6 + rd16(ip + 4)) & 0xffff) == 0x24e:
                    ops.append(('choose',)); regs['al'] = Sym(CHOICE); ip += 6; continue
                if 0x200 <= tgt < 0x400:
                    ops.append(('unk', 'call%x' % tgt)); ip += 3; continue
                if tgt == reg.ask_item:
                    ops.append(('choose',))
                    res = []
                    for wid, flg in ((0x39, 0x103), (0x3b, 0x105), (0x31, 0x104), (0x3c, 0x106)):
                        r2 = dict(regs); r2['al'] = wid; r2['bl'] = flg & 0xff; r2['bh'] = flg >> 8
                        r2['ch'] = 0
                        m2 = dict(mem); m2[CHOICE] = wid
                        res.append((wid, self.run_sub(ip + 3, m2, r2, cs, depth)))
                    r2 = dict(regs); r2['al'] = 0xff; m2 = dict(mem); m2[CHOICE] = 0xff
                    other = self.run_sub(ip + 3, m2, r2, cs, depth)
                    t = other
                    for wid, tr in reversed(res):
                        t = [('if', CHOICE, wid, tr, t)]
                    ops += t; return ops
                if tgt in reg.redraw:
                    ops.append(('redraw',)); ip += 3; continue
                if (tgt - 3) in reg.redraw and isinstance(regs.get('al'), int):
                    ops.append(('set', 0x101, regs['al'])); ops.append(('redraw',)); ip += 3; continue
                if tgt == reg.ask2:
                    ops.append(('ask2',)); regs['al'] = Sym(0x25c); ip += 3; continue
                cs.append(ip + 3); ip = tgt; continue
            if op in (0xc3, 0xcb):
                if cs: ip = cs.pop(); continue
                ops.append(('end',)); return ops
            if op == 0x50 or op == 0x53 or op == 0x51 or op == 0x52:
                # push; only the push bx / push bx; ret idiom matters, ignore otherwise
                cs.append(('push', ip)); ip += 1; continue
            raise Abort('opcode %02x at %x' % (op, ip))

    def run_sub(self, ip, mem, regs, cs, depth, neq=None, flags=None):
        if depth > 12: raise Abort('depth')
        return self.run(ip, mem, regs, cs, depth + 1, flags=flags)


def prune(tree, assign):
    """Resolve 'if' nodes using known memory assignments assign={addr:val}."""
    out = []
    for op in tree:
        if op[0] == 'if':
            _, a, v, t, e = op
            if a in assign:
                out += prune(t if assign[a] == v else e, assign)
                return out
            else:
                a2 = dict(assign); a2[a] = v
                out.append(('if', a, v, prune(t, a2), prune(e, assign)))
                return out
        if op[0] == 'iflt':
            out.append(('iflt', op[1], op[2], prune(op[3], assign), prune(op[4], assign)))
            return out
        out.append(op)
    return out


def collect_nouns(tree, acc):
    for op in tree:
        if op[0] == 'if':
            if op[1] == 0x25b: acc.add(op[2])
            collect_nouns(op[3], acc); collect_nouns(op[4], acc)
        elif op[0] == 'iflt':
            collect_nouns(op[3], acc); collect_nouns(op[4], acc)


