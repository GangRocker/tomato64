"""Write a standard 35-track D64 image containing PRG files."""

SPT = [21] * 17 + [19] * 7 + [18] * 6 + [17] * 5   # sectors per track, tracks 1..35


def _off(t, s):
    return (sum(SPT[:t - 1]) + s) * 256


def make_d64(files, disk_name='TOMATOHIME', disk_id='TH'):
    """files: list of (name, bytes)."""
    img = bytearray(174848)
    used = {(t, s): False for t in range(1, 36) for s in range(SPT[t - 1])}
    used[(18, 0)] = used[(18, 1)] = True

    def alloc(prefer_track):
        # simple interleave allocator starting near track 1 (skip 18)
        order = [t for t in range(1, 36) if t != 18]
        for t in order:
            n = SPT[t - 1]
            s = 0
            for _ in range(n):
                if not used[(t, s)]:
                    used[(t, s)] = True
                    return t, s
                s = (s + 10) % n
            for s in range(n):
                if not used[(t, s)]:
                    used[(t, s)] = True
                    return t, s
        raise Exception('disk full')

    entries = []
    for name, data in files:
        chain = []
        for i in range(0, len(data), 254):
            chain.append(alloc(1))
        blocks = [data[i:i + 254] for i in range(0, len(data), 254)] or [b'']
        for k, (t, s) in enumerate(chain):
            o = _off(t, s)
            if k + 1 < len(chain):
                img[o], img[o + 1] = chain[k + 1]
            else:
                img[o], img[o + 1] = 0, len(blocks[k]) + 1
            img[o + 2:o + 2 + len(blocks[k])] = blocks[k]
        entries.append((name, chain[0], len(chain)))

    # BAM
    o = _off(18, 0)
    img[o], img[o + 1], img[o + 2] = 18, 1, 0x41
    for t in range(1, 36):
        free = [s for s in range(SPT[t - 1]) if not used[(t, s)]]
        bits = 0
        for s in free: bits |= 1 << s
        p = o + 4 * t
        img[p] = len(free)
        img[p + 1:p + 4] = bits.to_bytes(3, 'little')
    nm = disk_name.upper().encode('ascii')[:16].ljust(16, b'\xa0')
    img[o + 0x90:o + 0xA0] = nm
    img[o + 0xA0:o + 0xA2] = b'\xa0\xa0'
    img[o + 0xA2:o + 0xA4] = disk_id.upper().encode('ascii')[:2].ljust(2, b'\xa0')
    img[o + 0xA4] = 0xA0
    img[o + 0xA5:o + 0xA7] = b'2A'
    img[o + 0xA7:o + 0xAB] = b'\xa0' * 4

    # directory: 8 entries per sector, chained on track 18
    order = [1, 4, 7, 10, 13, 16, 2, 5, 8, 11, 14, 17, 3, 6, 9, 12, 15, 18]
    nsec = max(1, (len(entries) + 7) // 8)
    if nsec > len(order): raise Exception('too many files')
    secs = order[:nsec]
    for k, sec in enumerate(secs):
        d = _off(18, sec)
        if k + 1 < nsec: img[d], img[d + 1] = 18, secs[k + 1]
        else: img[d], img[d + 1] = 0, 0xFF
        used[(18, sec)] = True
    for i, (name, (t, s), nblk) in enumerate(entries):
        e = _off(18, secs[i // 8]) + 32 * (i % 8)
        img[e + 2] = 0x82
        img[e + 3], img[e + 4] = t, s
        img[e + 5:e + 21] = name.upper().encode('ascii')[:16].ljust(16, b'\xa0')
        img[e + 0x1E:e + 0x20] = nblk.to_bytes(2, 'little')
    # track 18 BAM entry (directory sectors)
    o = _off(18, 0)
    free = [s for s in range(SPT[17]) if not used[(18, s)]]
    bits = 0
    for s in free: bits |= 1 << s
    img[o + 4 * 18] = len(free)
    img[o + 4 * 18 + 1:o + 4 * 18 + 4] = bits.to_bytes(3, 'little')
    return bytes(img)
