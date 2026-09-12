#!/usr/bin/env python3
"""
Decode an M-VAVE FM-1 bank-restore SysEx capture into standard DX7 banks.

Usage:
    fm1_decode.py capture.mmon [output_prefix]

Takes a MIDI Monitor saved log (.mmon) of the M-VAVE firmware tool performing
a factory preset restore, and writes standard Yamaha DX7 32-voice bank dumps
that Dexed, PocketMIDI or the FM-1 itself will accept.

FM-1 bank message format (observed on firmware v14 restore):
    F0 00 32 09 41 40 00 40 02 00 SS 00 00 00 00 01 | payload | CK F7
    SS   slot, 0x00..0x78 in steps of 8 (16 messages x 8 voices = 128)
    CK   single trailing byte, not required for decoding
    payload  1171 septets, LSB-first bitstream, unpacking to 1024 bytes
             = 8 standard 128-byte packed DX7 voices
"""
import plistlib, sys, os

HDR = 16          # bytes of message header before the payload
SLOT_BYTE = 9     # index of the slot number within the message body


def read_mmon(path):
    """Pull the raw SysEx bodies out of a MIDI Monitor saved log."""
    outer = plistlib.load(open(path, 'rb'))
    objs = plistlib.loads(outer['messageData'])['$objects']
    out = []
    for o in objs:
        if isinstance(o, dict) and 'data' in o and 'originatingEndpoint' in o:
            out.append(bytes(objs[o['data'].data]))
    return out


def unpack7(septets):
    """LSB-first 7-bit bitstream to 8-bit bytes."""
    bits = []
    for b in septets:
        for i in range(7):
            bits.append((b >> i) & 1)
    out = bytearray()
    for i in range(0, len(bits) - 7, 8):
        v = 0
        for j in range(8):
            v |= bits[i + j] << j
        out.append(v)
    return bytes(out)


def dx7_bank(voices_4096):
    """Wrap 4096 bytes of packed voices as a DX7 32-voice bank dump."""
    chk = (128 - (sum(voices_4096) & 0x7F)) & 0x7F
    return bytes([0xF0, 0x43, 0x00, 0x09, 0x20, 0x00]) + voices_4096 + bytes([chk, 0xF7])


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = sys.argv[1]
    prefix = sys.argv[2] if len(sys.argv) > 2 else 'FM-1_bank'

    blocks = [m for m in read_mmon(src) if len(m) > 1000]
    if len(blocks) != 16:
        print(f'warning: found {len(blocks)} bank messages, expected 16')
    blocks.sort(key=lambda m: m[SLOT_BYTE])

    data = b''.join(unpack7(m[HDR:-1]) for m in blocks)
    if len(data) % 128:
        sys.exit(f'decoded {len(data)} bytes, not a whole number of voices')
    if max(data) > 0x7F:
        sys.exit('decoded data contains bytes above 0x7F - alignment is wrong')

    n = len(data) // 128
    print(f'{n} voices decoded')
    for i in range(n):
        name = data[i * 128 + 118:i * 128 + 128].decode('ascii', 'replace')
        print(f'  {i:3d}  {name}')

    for bank in range(n // 32):
        body = data[bank * 4096:(bank + 1) * 4096]
        fn = f'{prefix}{bank + 1}.syx'
        open(fn, 'wb').write(dx7_bank(body))
        print(f'wrote {fn}')


if __name__ == '__main__':
    main()
