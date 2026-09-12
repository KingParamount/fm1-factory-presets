# M-VAVE FM-1 factory presets

The M-VAVE FM-1 receives SysEx but never sends it. Once you overwrite the factory presets with DX7 banks, they are gone: the onboard factory reset restores whatever was last imported, not the original set. The only route back is M-VAVE's Chinese-language updater, which also downgrades your firmware to v14.

This repository has the factory set recovered as four standard DX7 bank dumps, so you can put it back with Dexed, PocketMIDI or any SysEx utility, with no updater and no firmware downgrade.

## Restoring the factory presets

Send the four files in `banks/` to the FM-1, one per bank. They are ordinary Yamaha DX7 32-voice bank dumps, 4104 bytes each, so anything that can send a DX7 bank will do.

| File | Contents |
|---|---|
| `banks/FM-1_factory_bank1.syx` | PIANO, ORGAN, SYN LEAD, SYN PAD |
| `banks/FM-1_factory_bank2.syx` | GUITAR, DS GUITAR, BASS, SYN BASS |
| `banks/FM-1_factory_bank3.syx` | BRASS, WOODWIND, STRING, VOICE |
| `banks/FM-1_factory_bank4.syx` | Percussion and effects |

`banks/FM-1_factory_128voices_packed.bin` holds all 128 voices in DX7 packed format without the SysEx wrapper, for anyone wanting to do their own analysis.

## Where the presets came from

126 of the 128 voices are byte-identical to patches in BlackWinny's Dexed_cart 1.0 compilation. A 127th is one byte away. 40 also trace to genuine Yamaha DX7 ROM and VRC cartridges.

The naming follows the folder each patch was found in rather than the patch itself, which is why DX7's BANJO appears as GUITAR 3 and ACCORDION as WOODWIND 7.

Full per-voice table in [`docs/protocol-and-provenance.md`](docs/protocol-and-provenance.md), with a printable version at [`docs/FM-1-provenance.pdf`](docs/FM-1-provenance.pdf).

## The protocol

`docs/protocol-and-provenance.md` documents the FM-1's bank-transfer SysEx, including the device handshake, the sixteen-message bank restore, and the 7-bit payload encoding. Short version: manufacturer ID `00 32`, sixteen messages of eight voices each, and a payload that is an LSB-first 7-bit bitstream rather than either of the two conventional MIDI packing schemes.

## Tools

| Script | Does |
|---|---|
| `tools/fm1_decode.py` | Turns a MIDI Monitor `.mmon` capture of a preset restore into DX7 banks |
| `tools/fm1_compare.py` | Compares a packed voice dump against reference banks |
| `tools/get_dx7_factory.sh` | Fetches all 32 Yamaha DX7 factory cartridges for comparison |

Python 3, no dependencies beyond the standard library.

## Capturing your own

On macOS, traffic sent to a MIDI destination is invisible to other applications, so an ordinary port monitor shows nothing. Use Snoize's MIDI Monitor, enable "spy on output to destinations" in its Sources pane, install the helper when prompted, restart, then tick the FM-1 under destinations. Clear the log, press restore in the updater, and save the result. Then:

```
python3 tools/fm1_decode.py your_capture.mmon
```

## Credits

The patches themselves are the work of the DX7 community over several decades. BlackWinny (Jacques Prestreau) compiled and deduplicated the collection they were traced to. Dexed by asb2m10 was used throughout for verification, and its credits list many of the individual patch authors.
