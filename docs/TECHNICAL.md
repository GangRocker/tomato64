# Technical notes

## Source disks

Two images are accepted (`tools/source.py` detects which):

- **Original Hudson release** (5.25" 2DD, self-booting, 16 x 256-byte sectors per track). The game uses only every
  fourth track (cylinder 2n, side 0); concatenated, these form a 160 KB logical disk. Region files are whole logical
  tracks: B = 3-13, C = 14-19, D = 20-27, A = 28-38, each loaded at $3000.
- **2HD N88-BASIC copy** (files `SARADAP0`-`P4`), described below. Its game data is identical; only the loader and
  unused areas differ.

### 2HD N88-BASIC(86) format

- 77 cylinders x 2 heads, 26 sectors x 256 bytes (cylinder 0 head 0: 26 x 128 bytes).
- Directory: cylinder 35 head 0 (track 70), 16-byte entries (name 6 + ext 3 + attribute + first cluster).
- FAT: sector 24 of the directory track. One cluster = one track side (6656 bytes). Entry values >= $C0 mark the last
  cluster (low bits = sectors used). Several files are stored on clusters in *descending* order.
- Game files: `SARADAP0` (runtime), `SARADAP1`..`P4` (scene groups B, C, D, A), each with a 4-byte header
  (load offset $3000, end). Scene groups: B = scenes 0-49, C = 50-76, D = 77-106, A = 107-153.

## Scene records

13-byte header (custom-direction flag, four direction handler pointers, four exits), list 1 (noun, handler) for
"look", list 2 (verb, flag, handler) for other verbs, then 8086 code. The converter runs every handler with a small
symbolic 8086 executor (`tools/sym.py`): runtime calls (print, goto scene, ask for an item, ...) become operations and
tests on flag memory become `if` nodes (equality) and `iflt` nodes (unsigned `flag < k`, from `cmp`+`jb/jae/jbe/ja`). Unreachable/unknown parts are reported as "unresolved handlers".

Direction handlers that point to the driver's "you cannot go that way" routine are not offered in the C64 menu.

Menu adaptations of the typed parser (all in `tools/encode.py`):
- a noun is hidden while the item is not held when the original rule refuses with "you don't have it";
- a verb whose nouns are all hidden is not offered;
- answers that need a typed word ("which colour?", the survey password) are offered only after the hint was heard;
- commands that required a tool word ("X with Y") ask for the tool ("ﾅﾆｦ ﾂｶｯﾃ");
- the new-game state (starting items) comes from the original (value, address) table.

## Pictures

Original routine (runtime $138E): canvas cleared to white, then records until `(cmd & $C0) == 0`:

| cmd & $C0 | bytes | meaning |
|---|---|---|
| $40 | 3 | move to x = (cmd & 3) << 8 \| b1, y = b2 |
| $80 | 3 | line to (x, y), colour = (cmd >> 3) & 7 |
| $C0 | 4 | flood fill from (x, y) with 2-colour pattern b3 (high/low nibble) |

Coordinates are 640x168. Pointer tables: B $4FC7, C $3645, D $35EE, A $4B00.

## C64 engine

- Memory: engine $0810-, room file at $3400 (u16 length, room data at $3402, then the picture; max 4 KB), event pictures $5000,
  flags $5F00, screen $4400, font $4800, bitmap $6000, render buffer $8000-$CFFF + $E000-$F8FF (RAM banked in while
  drawing, raster IRQ keeps running from a RAM vector).
- Raster split: multicolour bitmap for rows 0-20, text for rows 21-24; background is always black so nothing changes
  colour at the split.
- Renderer: Bresenham lines and scanline flood fill into a 160x168 byte-per-pixel buffer; changed 4x8 cells are
  converted to multicolour (black + 3 most frequent colours) about five times a second, so the drawing is visible.
- Room data: verb table (id, mode, noun list), rules (verb, noun, visibility flag, script), scripts.
- Room data: texts used more than once in a room are stored once in a string pool.
- Script VM ops: 0 end, 1 text, 2 set, 3 if-not-equal (skip16), 4 goto, 5 wait key, 6 if-less-than (skip16),
  7 pooled text, 9 jump16, 10 add, 11 toggle, 12 choose item (candidates inline), 13 "cannot do", 14 show event picture.
- Music: SID player called once per frame from the raster IRQ; PAL/NTSC detected at start (pitch table, NTSC skips
  one frame in six). Paused during disk access. Song data and the scene-to-song table: `tools/music.py`.
- Translations (`--lang en|es`): strings are replaced at build time from `lang/*.json` (key = first 16 hex digits of
  SHA-1 of the original string). The engine then word-wraps (`WRAPON`), copies Latin letters from the character ROM
  at start-up, and the Spanish build adds 10 glyphs at $80-$89.
- Save file `TOMATOSAV`: 256 bytes of flags, last byte = current scene.
