#!/usr/bin/env python3
"""
Compare decoded FM-1 factory voices against genuine Yamaha DX7 cartridge banks.

Usage:
    fm1_compare.py FM-1_factory_128voices_packed.bin rom*.syx

Reference banks are the DX7 factory ROM and VRC cartridge dumps, e.g. from
    https://yamahablackboxes.com/collection/yamaha-dx7-synthesizer/patches/
(the same source MiniDexed's getsysex.sh uses).

For each FM-1 voice it reports the closest reference voice, comparing the
112 bytes of parameter data separately from the 10-byte name, so you can see
whether M-VAVE copied the patches, only the names, or neither.
"""
import sys, os, glob

PARAM, NAME = slice(0, 112), slice(118, 128)


def load_ref(paths):
    refs = []
    for p in paths:
        d = open(p, 'rb').read()
        # a 32-voice bank dump is 4104 bytes: 6 header, 4096 data, checksum, F7
        if len(d) == 4104 and d[0] == 0xF0:
            body = d[6:6 + 4096]
        elif len(d) == 4096:
            body = d
        else:
            print(f'skipping {p} ({len(d)} bytes, not a 32-voice bank)')
            continue
        tag = os.path.splitext(os.path.basename(p))[0]
        for i in range(32):
            refs.append((f'{tag}:{i:02d}', body[i * 128:(i + 1) * 128]))
    return refs


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    src = open(sys.argv[1], 'rb').read()
    paths = [q for a in sys.argv[2:] for q in glob.glob(a)]
    refs = load_ref(paths)
    if not refs:
        sys.exit('no reference banks loaded')
    print(f'{len(src)//128} FM-1 voices vs {len(refs)} reference voices\n')

    exact_param = exact_name = 0
    for i in range(len(src) // 128):
        v = src[i * 128:(i + 1) * 128]
        # closest reference by parameter-byte differences
        best = min(refs, key=lambda r: sum(a != b for a, b in zip(v[PARAM], r[1][PARAM])))
        diff = sum(a != b for a, b in zip(v[PARAM], best[1][PARAM]))
        # any reference sharing this name, ignoring spaces and case
        key = v[NAME].decode('ascii', 'replace').replace(' ', '').upper()
        nm = [r for r in refs
              if r[1][NAME].decode('ascii', 'replace').replace(' ', '').upper() == key]
        if diff == 0:
            exact_param += 1
        if nm:
            exact_name += 1
        print(f'{i:3d} {v[NAME].decode("ascii","replace")}  '
              f'closest {best[0]} diff {diff:3d}/112  '
              f'name match: {nm[0][0] if nm else "-"}')

    n = len(src) // 128
    print(f'\nidentical parameter data: {exact_param}/{n}')
    print(f'exact name match (spaces/case ignored): {exact_name}/{n}')


if __name__ == '__main__':
    main()
