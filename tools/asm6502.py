"""Minimal 2-pass 6502 assembler (official opcodes only)."""
import re

_T = """
ADC imm69 zp65 zpx75 abs6D abx7D aby79 izx61 izy71
AND imm29 zp25 zpx35 abs2D abx3D aby39 izx21 izy31
ASL acc0A zp06 zpx16 abs0E abx1E
BCC rel90
BCS relB0
BEQ relF0
BIT zp24 abs2C
BMI rel30
BNE relD0
BPL rel10
BRK imp00
BVC rel50
BVS rel70
CLC imp18
CLD impD8
CLI imp58
CLV impB8
CMP immC9 zpC5 zpxD5 absCD abxDD abyD9 izxC1 izyD1
CPX immE0 zpE4 absEC
CPY immC0 zpC4 absCC
DEC zpC6 zpxD6 absCE abxDE
DEX impCA
DEY imp88
EOR imm49 zp45 zpx55 abs4D abx5D aby59 izx41 izy51
INC zpE6 zpxF6 absEE abxFE
INX impE8
INY impC8
JMP abs4C ind6C
JSR abs20
LDA immA9 zpA5 zpxB5 absAD abxBD abyB9 izxA1 izyB1
LDX immA2 zpA6 zpyB6 absAE abyBE
LDY immA0 zpA4 zpxB4 absAC abxBC
LSR acc4A zp46 zpx56 abs4E abx5E
NOP impEA
ORA imm09 zp05 zpx15 abs0D abx1D aby19 izx01 izy11
PHA imp48
PHP imp08
PLA imp68
PLP imp28
ROL acc2A zp26 zpx36 abs2E abx3E
ROR acc6A zp66 zpx76 abs6E abx7E
RTI imp40
RTS imp60
SBC immE9 zpE5 zpxF5 absED abxFD abyF9 izxE1 izyF1
SEC imp38
SED impF8
SEI imp78
STA zp85 zpx95 abs8D abx9D aby99 izx81 izy91
STX zp86 zpy96 abs8E
STY zp84 zpx94 abs8C
TAX impAA
TAY impA8
TSX impBA
TXA imp8A
TXS imp9A
TYA imp98
"""
OPS = {}   # mnemonic -> {mode: opcode}
for line in _T.strip().splitlines():
    p = line.split()
    OPS[p[0]] = {x[:-2] if x[:3] in ('imm', 'abs', 'abx', 'aby', 'izx', 'izy', 'imp', 'acc', 'rel', 'ind') and len(x) == 5 else None: None for x in []}
    d = {}
    for x in p[1:]:
        m = re.match(r'(zpx|zpy|zp|imm|abs|abx|aby|izx|izy|imp|acc|rel|ind)([0-9A-F]{2})$', x)
        d[m.group(1)] = int(m.group(2), 16)
    OPS[p[0]] = d
SIZE = {'imp': 1, 'acc': 1, 'imm': 2, 'zp': 2, 'zpx': 2, 'zpy': 2, 'izx': 2, 'izy': 2, 'rel': 2,
        'abs': 3, 'abx': 3, 'aby': 3, 'ind': 3}


class AsmError(Exception):
    pass


def _num(tok):
    return tok


class Asm:
    def __init__(self):
        self.sym = {}
        self.out = bytearray()
        self.org = None

    # ---- expression --------------------------------------------------
    def ev(self, s, pc, final):
        s = s.strip()
        if not s:
            raise AsmError('empty expr')
        hi = lo = False
        if s[0] == '<':
            lo = True; s = s[1:]
        elif s[0] == '>':
            hi = True; s = s[1:]

        def repl(m):
            t = m.group(0)
            if t == '*':
                return str(pc)
            if t.startswith('$'):
                return str(int(t[1:], 16))
            if t.startswith('%'):
                return str(int(t[1:], 2))
            if re.match(r'\d', t):
                return t
            if t in self.sym:
                return str(self.sym[t])
            if final:
                raise AsmError('undefined symbol ' + t)
            return '0'
        s = re.sub(r"(?<![\w)$])\*(?![\w($])", str(pc), s)
        e = re.sub(r"\$[0-9A-Fa-f]+|%[01]+|[A-Za-z_.][A-Za-z_0-9.]*|\d+", repl, s)
        v = int(eval(e, {'__builtins__': {}}, {}))
        if lo: v &= 0xFF
        if hi: v = (v >> 8) & 0xFF
        return v

    # ---- parse operand -------------------------------------------------
    def operand(self, m, op, pc, final):
        modes = OPS[m]
        if op is None or op == '':
            return ('imp' if 'imp' in modes else 'acc'), None
        if op.upper() == 'A' and 'acc' in modes:
            return 'acc', None
        if op.startswith('#'):
            return 'imm', self.ev(op[1:], pc, final)
        mm = re.match(r'\((.*),\s*[xX]\)$', op)
        if mm: return 'izx', self.ev(mm.group(1), pc, final)
        mm = re.match(r'\((.*)\)\s*,\s*[yY]$', op)
        if mm: return 'izy', self.ev(mm.group(1), pc, final)
        mm = re.match(r'\((.*)\)$', op)
        if mm: return 'ind', self.ev(mm.group(1), pc, final)
        idx = None
        mm = re.match(r'(.*),\s*([xXyY])$', op)
        if mm:
            op, idx = mm.group(1), mm.group(2).lower()
        v = self.ev(op, pc, final)
        if 'rel' in modes:
            return 'rel', v
        zp_ok = v < 256 and self._known(op)
        if idx == 'x':
            return ('zpx' if zp_ok and 'zpx' in modes else 'abx'), v
        if idx == 'y':
            return ('zpy' if zp_ok and 'zpy' in modes else 'aby'), v
        return ('zp' if zp_ok and 'zp' in modes else 'abs'), v

    def _known(self, expr):
        # zero page only if every symbol is already defined (pass 2 or earlier definition)
        for t in re.findall(r"[A-Za-z_.][A-Za-z_0-9.]*", expr):
            if t not in self.sym:
                return False
        return True

    # ---- assembling ------------------------------------------------------
    def assemble(self, src, base=None):
        lines = []
        for n, raw in enumerate(src.splitlines(), 1):
            # strip comments (not inside quotes)
            out = ''; q = False
            for ch in raw:
                if ch == '"': q = not q
                if ch == ';' and not q: break
                out += ch
            lines.append((n, out.rstrip()))
        # pass 1 gathers symbols; pass 2 emits
        # constants (NAME = expr) are evaluated in-order in both passes
        for pas in (1, 2):
            final = pas == 2
            pc = base if base is not None else 0
            buf = bytearray()
            origin = base
            if pas == 2:
                sym_final = dict(self.sym)
            for n, line in lines:
                try:
                    pc, origin = self._line(line, pc, buf, origin, final)
                except AsmError as e:
                    raise AsmError(f'line {n}: {e}: {line.strip()}')
            if pas == 2:
                self.out = buf; self.org = origin
        return self.org, bytes(self.out)

    def _line(self, line, pc, buf, origin, final):
        s = line.strip()
        if not s:
            return pc, origin
        # label(s)
        while True:
            mm = re.match(r'([A-Za-z_.][A-Za-z_0-9.]*):\s*(.*)$', s)
            if not mm: break
            self.sym[mm.group(1)] = pc
            s = mm.group(2)
        if not s:
            return pc, origin
        mm = re.match(r'([A-Za-z_.][A-Za-z_0-9.]*)\s*=\s*(.*)$', s)
        if mm and not s.startswith('*'):
            self.sym[mm.group(1)] = self.ev(mm.group(2), pc, final)
            return pc, origin
        if s.startswith('*'):
            mm = re.match(r'\*\s*=\s*(.*)$', s)
            v = self.ev(mm.group(1), pc, final)
            if origin is None or (not buf and origin == 0):
                origin = v; pc = v
            else:
                if v < pc: raise AsmError('org backwards')
                buf.extend(b'\x00' * (v - pc)); pc = v
            return pc, origin
        parts = s.split(None, 1)
        m = parts[0].upper(); rest = parts[1].strip() if len(parts) > 1 else ''
        if m.startswith('.'):
            if m == '.BYTE':
                for item in self._split(rest):
                    if item.startswith('"'):
                        b = item[1:-1].encode('latin-1')
                        buf.extend(b); pc += len(b)
                    else:
                        buf.append(self.ev(item, pc, final) & 0xFF); pc += 1
            elif m == '.WORD':
                for item in self._split(rest):
                    v = self.ev(item, pc, final)
                    buf.extend([v & 0xFF, (v >> 8) & 0xFF]); pc += 2
            elif m == '.FILL':
                a = self._split(rest)
                n = self.ev(a[0], pc, final); v = self.ev(a[1], pc, final) if len(a) > 1 else 0
                buf.extend(bytes([v & 0xFF]) * n); pc += n
            elif m == '.INCBIN':
                data = open(rest.strip('"'), 'rb').read()
                buf.extend(data); pc += len(data)
            elif m == '.ALIGN':
                a = self.ev(rest, pc, final)
                while pc % a: buf.append(0); pc += 1
            else:
                raise AsmError('unknown directive ' + m)
            return pc, origin
        if m not in OPS:
            raise AsmError('unknown mnemonic ' + m)
        mode, v = self.operand(m, rest, pc, final)
        modes = OPS[m]
        if mode not in modes:
            if mode == 'zp' and 'abs' in modes: mode = 'abs'
            elif mode == 'acc' and 'imp' in modes: mode = 'imp'
            else: raise AsmError(f'bad addressing mode {mode} for {m}')
        op = modes[mode]
        if mode == 'rel':
            off = v - (pc + 2)
            if final and not -128 <= off <= 127:
                raise AsmError(f'branch out of range ({off})')
            buf.extend([op, off & 0xFF])
        elif SIZE[mode] == 1:
            buf.append(op)
        elif SIZE[mode] == 2:
            if final and not 0 <= v < 256 and mode != 'imm':
                raise AsmError('operand out of range')
            buf.extend([op, v & 0xFF])
        else:
            buf.extend([op, v & 0xFF, (v >> 8) & 0xFF])
        return pc + SIZE[mode], origin

    @staticmethod
    def _split(s):
        items = []; cur = ''; q = False
        for ch in s:
            if ch == '"': q = not q
            if ch == ',' and not q:
                items.append(cur.strip()); cur = ''
            else:
                cur += ch
        if cur.strip(): items.append(cur.strip())
        return items
