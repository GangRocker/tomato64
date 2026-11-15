"""Original background music for the C64 version (composed for this port; not taken from any game).

Each song has three voice streams. Stream bytes:
  $00            rest (for the current length)
  $01-$54        note (1 = C0 ... 84 = B6)
  $80+len        set note length in ticks (1-63)
  $C0+i          select instrument i
  $FD            fade the master volume out (song stops at volume 0)
  $FE            loop to the start of this voice
  $FF            voice ends
A tick lasts `speed` frames (PAL timing; the player skips one frame in six on NTSC).
"""

NAMES = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}

# instruments: waveform control (gate bit added by the player), attack/decay, sustain/release, pulse width high
INSTR = [
    (0x41, 0x09, 0xA4, 0x06),   # 0 lead (pulse)
    (0x11, 0x06, 0xA6, 0x00),   # 1 bass (triangle)
    (0x41, 0x29, 0x55, 0x08),   # 2 soft chords (square)
    (0x11, 0x2A, 0x96, 0x00),   # 3 soft lead (triangle)
    (0x21, 0x28, 0xA6, 0x00),   # 4 brass (sawtooth)
    (0x21, 0x0A, 0x88, 0x00),   # 5 sad (sawtooth)
    (0x41, 0x08, 0x86, 0x02),   # 6 thin lead (narrow pulse)
]


def note(n):
    """'C5' -> note number (C0 = 1)."""
    name, octv = n[:-1], int(n[-1])
    v = octv * 12 + NAMES[name] + 1
    assert 1 <= v <= 84, n
    return v


def seq(text):
    """'i0 C5/4 E5/4 r/4' -> list of (kind, value, length) events."""
    ev = []
    for tok in text.split():
        if tok == 'fade':
            ev.append(('f', 0, 0))
            continue
        if tok[0] == 'i':
            ev.append(('i', int(tok[1:]), 0))
            continue
        n, ln = tok.split('/')
        ev.append(('r' if n == 'r' else 'n', 0 if n == 'r' else note(n), int(ln)))
    return ev


def ticks(ev):
    return sum(l for k, v, l in ev if k not in ('i', 'f'))


def compile_voice(ev, loop=True):
    out = bytearray()
    cur = None
    for k, v, l in ev:
        if k == 'i':
            out.append(0xC0 + v)
            continue
        if k == 'f':
            out.append(0xFD)
            continue
        while l > 0:
            part = min(l, 63)
            if part != cur:
                out.append(0x80 + part); cur = part
            out.append(v if k == 'n' else 0)
            l -= part
            if l and k == 'n':        # long notes are split into a note and rests (keeps the release)
                k = 'r'; v = 0
    out.append(0xFE if loop else 0xFF)
    return bytes(out)


def bass_bars(chords, pattern):
    """chords: list of root note names per bar; pattern: list of (semitone offset, length)."""
    s = []
    for root in chords:
        r = note(root)
        for off, ln in pattern:
            s.append(('r', 0, ln) if off is None else ('n', r + off, ln))
    return s


def arp_bars(chords, pattern):
    """chords: list of tuples of note names; pattern: list of (index into chord or None, length)."""
    s = []
    for ch in chords:
        for idx, ln in pattern:
            s.append(('r', 0, ln) if idx is None else ('n', note(ch[idx]), ln))
    return s


# ------------------------------------------------------------------ 0: title theme (C major, lively)
T_MEL = seq('i0 '
            'G4/4 C5/4 E5/4 G5/4  F5/6 E5/2 D5/4 C5/4  D5/4 E5/4 F5/4 A5/4  G5/12 r/4 '
            'A5/4 G5/4 F5/4 E5/4  D5/6 E5/2 F5/4 D5/4  C5/4 E5/4 D5/4 B4/4  C5/12 r/4 '
            'E5/4 E5/4 F5/4 G5/4  A5/8 G5/8  F5/4 F5/4 E5/4 D5/4  E5/8 C5/8 '
            'D5/4 D5/4 E5/4 F5/4  G5/6 F5/2 E5/4 D5/4  C5/4 E5/4 G5/4 E5/4  C5/12 r/4')
T_ROOTS = ['C3', 'F2', 'D3', 'G2', 'F2', 'D3', 'C3', 'C3',
           'C3', 'F2', 'D3', 'A2', 'G2', 'G2', 'C3', 'C3']
T_CH = [('E4', 'G4'), ('F4', 'A4'), ('F4', 'A4'), ('D4', 'G4'), ('F4', 'A4'), ('F4', 'A4'), ('E4', 'G4'), ('E4', 'G4'),
        ('E4', 'G4'), ('F4', 'A4'), ('F4', 'A4'), ('E4', 'A4'), ('D4', 'G4'), ('D4', 'F4'), ('E4', 'G4'), ('E4', 'G4')]
T_BASS = [('i', 1, 0)] + bass_bars(T_ROOTS, [(0, 4), (7, 4), (12, 4), (7, 4)])
T_ARP = [('i', 2, 0)] + arp_bars(T_CH, [(None, 2), (0, 2), (None, 2), (1, 2)] * 2)

# ------------------------------------------------------------------ 1: field (G major, gentle)
F_MEL = seq('i3 '
            'B4/4 D5/4 G5/8  F#5/4 E5/4 D5/8  C5/4 E5/4 A5/6 G5/2  F#5/12 r/4 '
            'G5/4 F#5/4 E5/4 D5/4  C5/4 B4/4 A4/8  B4/4 C5/4 D5/4 F#5/4  G5/12 r/4')
F_ROOTS = ['G2', 'D3', 'A2', 'D3', 'G2', 'C3', 'D3', 'G2']
F_CH = [('G3', 'B3', 'D4'), ('D3', 'F#3', 'A3'), ('A3', 'C4', 'E4'), ('D3', 'F#3', 'A3'),
        ('G3', 'B3', 'D4'), ('C3', 'E3', 'G3'), ('D3', 'F#3', 'A3'), ('G3', 'B3', 'D4')]
F_BASS = [('i', 1, 0)] + bass_bars(F_ROOTS, [(0, 8), (7, 8)])
F_ARP = [('i', 2, 0)] + arp_bars(F_CH, [(0, 2), (1, 2), (2, 2), (1, 2)] * 2)

# ------------------------------------------------------------------ 2: game over (once)
G_MEL = seq('i5 E5/4 D#5/4 D5/4 C#5/4 fade C5/24 r/8')
G_BASS = seq('i1 C3/16 C2/24 r/8')
G_ARP = seq('i2 G4/16 D#4/24 r/8')

# ------------------------------------------------------------------ 3: ending fanfare (C major)
E_MEL = seq('i4 '
            'G4/2 G4/2 G4/2 C5/10  E5/2 E5/2 E5/2 G5/10  A5/4 G5/4 F5/4 E5/4  D5/4 E5/4 F5/4 D5/4 '
            'C5/4 E5/4 G5/4 C6/4  B5/4 G5/4 A5/4 B5/4  C6/16  r/16')
E_ROOTS = ['C3', 'C3', 'F2', 'G2', 'C3', 'G2', 'C3', 'C3']
E_CH = [('E4', 'G4'), ('G4', 'C5'), ('F4', 'A4'), ('F4', 'B4'), ('E4', 'G4'), ('D4', 'G4'), ('E4', 'G4'), ('E4', 'G4')]
E_BASS = [('i', 1, 0)] + bass_bars(E_ROOTS, [(0, 4), (12, 4), (7, 4), (12, 4)])
E_ARP = [('i', 2, 0)] + arp_bars(E_CH, [(0, 4), (1, 4), (0, 4), (1, 4)])

# ------------------------------------------------------------------ 4: danger (A minor)
D_MEL = seq('i6 '
            'E5/8 D5/4 C5/4  B4/8 C5/4 A4/4  F5/8 E5/4 D5/4  E5/12 G#4/4 '
            'A5/8 G5/4 E5/4  F5/8 E5/4 D5/4  C5/4 D5/4 B4/4 G#4/4  A4/12 r/4')
D_ROOTS = ['A2', 'A2', 'F2', 'E2', 'A2', 'D2', 'E2', 'A2']
D_BASS = [('i', 1, 0)] + bass_bars(D_ROOTS, [(0, 2), (0, 2), (12, 2), (0, 2), (7, 2), (0, 2), (12, 2), (0, 2)])
D_CH = [('C4', 'E4'), ('C4', 'E4'), ('C4', 'F4'), ('B3', 'E4'), ('C4', 'E4'), ('D4', 'F4'), ('B3', 'E4'), ('C4', 'E4')]
D_ARP = [('i', 2, 0)] + arp_bars(D_CH, [(None, 4), (0, 2), (None, 2), (None, 4), (1, 2), (None, 2)])

SONGS = [
    # (voices, speed, loop)
    ((T_MEL, T_BASS, T_ARP), 6, True),
    ((F_MEL, F_BASS, F_ARP), 8, True),
    ((G_MEL, G_BASS, G_ARP), 8, False),
    ((E_MEL, E_BASS, E_ARP), 7, True),
    ((D_MEL, D_BASS, D_ARP), 6, True),
]
TITLE, FIELD, GAMEOVER, ENDING, DANGER = range(5)

GAMEOVER_SCENES = {85, 119, 124, 136, 140, 152, 153}
ENDING_SCENES = {145, 146, 147, 148, 149, 150, 151}
DANGER_SCENES = {81, 82, 83, 103, 104, 105, 142, 143, 144}


def scene_music(sid):
    if sid in GAMEOVER_SCENES: return GAMEOVER
    if sid in ENDING_SCENES: return ENDING
    if sid in DANGER_SCENES: return DANGER
    return FIELD


def freq_tables():
    """octave-6 frequency register values (C6..B6) for PAL and NTSC."""
    out = {}
    for name, clock in (('pal', 985248.0), ('ntsc', 1022727.0)):
        vals = []
        for semi in range(12):
            hz = 440.0 * 2 ** ((6 * 12 + semi - (4 * 12 + 9)) / 12.0)
            vals.append(int(round(hz * 16777216 / clock)))
        out[name] = vals
    return out


def asm(nscenes):
    for voices, speed, loop in SONGS:
        lens = [ticks([e for e in v]) for v in voices]
        assert len(set(lens)) == 1, ('voice lengths differ', lens)
    t = []
    ft = freq_tables()
    for k in ('pal', 'ntsc'):
        t.append('mfq_%s_lo: .byte %s\n' % (k, ','.join('<%d' % v for v in ft[k])))
        t.append('mfq_%s_hi: .byte %s\n' % (k, ','.join('>%d' % v for v in ft[k])))
    t.append('mins: .byte %s\n' % ','.join('$%02x,$%02x,$%02x,$%02x' % i for i in INSTR))
    t.append('msongs:\n')
    for i, (voices, speed, loop) in enumerate(SONGS):
        t.append('        .word ms%d_0,ms%d_1,ms%d_2\n        .byte %d\n' % (i, i, i, speed))
    for i, (voices, speed, loop) in enumerate(SONGS):
        for j, v in enumerate(voices):
            b = compile_voice(v, loop)
            t.append('ms%d_%d: .byte %s\n' % (i, j, ','.join('$%02x' % x for x in b)))
    t.append('roommus: .byte %s\n' % ','.join(str(scene_music(s)) for s in range(nscenes)))
    return ''.join(t)


if __name__ == '__main__':
    print(asm(154)[:2000])
    print(sum(len(compile_voice(v, l)) for vs, s, l in SONGS for v in vs), 'bytes of song data')
