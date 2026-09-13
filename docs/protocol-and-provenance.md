# Recovering the M-VAVE FM-1 factory presets, and finding out where they came from

The FM-1 receives SysEx but never sends it. You can push DX7 banks into it, and once you have, the factory sounds are gone. The onboard factory reset does not help, since it restores whatever was last imported rather than the original set.

The only way back is M-VAVE's own Windows tool. There are two builds: the English one updates the firmware but has no preset restore, and the Chinese-language one restores presets but downgrades you to firmware v14. Neither gives you a file you can keep.

This is a capture and decode of what that tool sends, the resulting banks as standard DX7 SysEx, and a trace of where the 128 factory voices originally came from.

## Capturing the restore

On macOS, outbound traffic to a MIDI destination is not visible to other applications, so a port monitor that only reads sources will show nothing. Snoize's MIDI Monitor has a spy driver that hooks the destination side. Enable "spy on output to destinations" in its Sources pane, install the helper when prompted, restart the app, then tick the FM-1 under destinations.

With the FM-1 connected over USB and the log cleared, pressing restore in the Chinese tool produces 48 SysEx rows in about 200 milliseconds. Four of those are the identify message appearing on IAC Driver Bus 1, which is the tool polling every MIDI destination it can see rather than FM-1 traffic. The remaining 44 are the restore itself.

## The protocol

M-VAVE use manufacturer ID `00 32`, not Yamaha's `43`, so none of it is
DX7-compatible on the wire. The byte after `00 32` differs by message type:
`45` for identify, `05` for setup, `09` for a voice block and `01` for an
acknowledgement. A device with four manufacturer IDs is unlikely, so it reads
as a command byte, though nothing in the capture confirms that.

The 44 messages of the restore break down as follows:

| Count | Direction   | Message      |
| ----- | ----------- | ------------ |
| 2     | host to FM-1 | identify     |
| 2     | FM-1 to host | identity reply |
| 4     | host to FM-1 | setup        |
| 4     | FM-1 to host | acknowledgement |
| 16    | host to FM-1 | voice block  |
| 16    | FM-1 to host | acknowledgement |

The tool identifies the device first, and does so twice in a row before moving
on:
-> F0 00 32 45 00 00 00 40 7F F7 <- F0 00 32 45 58 01 00 00 23 4D 5A 44 79 05 26 4C 1A 00 ... 20 06 F7


The reply is 41 bytes, mostly zeros. It contains the ASCII string `#MZD`
followed by five bytes that may be a version, a serial, or both. Anyone
publishing their own capture may want to mask those.

Four setup messages follow, each acknowledged:

-> F0 00 32 05 29 00 00 40 02 00 00 00 00 20 1F F7 -> F0 00 32 05 29 00 00 40 02 00 20 00 00 20 1D F7 -> F0 00 32 05 29 00 00 40 02 00 40 00 00 20 1B F7 -> F0 00 32 05 29 00 00 40 02 00 60 00 00 20 19 F7 <- F0 00 32 01 08 00 00 00 00 7F 01 F7 (ack, after each)

Only the tenth byte changes, running `00 20 40 60`. Those are slots 0, 32, 64
and 96, one per bank of 32 voices, addressed the same way the voice blocks are.
What the message asks the device to do is unknown. Nothing else in the four
is published anywhere, and none of it has been tested.

Then the voice data, sixteen messages, each acknowledged before the next is
sent:

-> F0 00 32 09 41 40 00 40 02 00 SS 00 00 00 00 01 00 | payload | CK F7 (1190 bytes) <- F0 00 32 01 08 00 00 00 00 7F 01 F7 (ack)


`SS` is the target slot, running `00 08 10 18 ... 78`. Sixteen messages of
eight voices each covers all 128 presets.

The message is `F0`, a 16-byte header, 1171 payload bytes, one checksum byte
and `F7`, which is 1190. How `CK` is calculated is not known. Summing and
XORing the header, the payload or the decoded data, in both plain and
two's-complement form, produces nothing that matches across all sixteen
blocks.

The 1171 payload bytes are a continuous 7-bit bitstream, LSB-first at both the
septet and the reassembled-byte level, which unpacks to exactly 1024 bytes.
Neither of the two conventional MIDI packing schemes will decode it: not the
byte-aligned MSB-group format used by Roland and Akai, and not an MSB-first
bitstream.

Those 1024 bytes are eight standard 128-byte packed DX7 voices. Algorithm,
feedback and transpose all sit at their usual offsets and fall within legal
ranges, and the ten-character name field lands at byte 118 of each voice. The
header length is confirmed by the decode rather than by counting: at 16 bytes
the first block reads PIANO 1, ORGAN 1, SYN LEAD 1, and at 15 or 17 it reads
nothing at all.

The signature that gives away the packing is a run like
`0C 1B 36 6C 58 31 63 46` inside the raw payload. Each value is the previous
one doubled with carry, which is what a byte-aligned pattern looks like after
being re-windowed into 7-bit chunks.

## Rebuilding as DX7 banks

Since the voices are already in DX7 packed format, there is no need to reimplement M-VAVE's transport. Concatenate the sixteen decoded blocks into 16384 bytes, split into four groups of 4096, and wrap each as a standard 32-voice bank dump:

```
F0 43 00 09 20 00 <4096 bytes> <checksum> F7
```

Checksum is `(128 - (sum & 0x7F)) & 0x7F`. The FM-1 accepts DX7 bank imports, so these load straight back in, as do Dexed and PocketMIDI.

The four banks:

| Bank | Contents |
|---|---|
| 1 | PIANO, ORGAN, SYN LEAD, SYN PAD, eight of each |
| 2 | GUITAR, DS GUITAR, BASS, SYN BASS |
| 3 | BRASS, WOODWIND, STRING, VOICE |
| 4 | Percussion and effects, original names retained |

Note the ordering. Each bank interleaves its four categories rather than grouping them, so slot order runs PIANO 1, ORGAN 1, SYN LEAD 1, SYN PAD 1, PIANO 2, and so on.

## Where the voices came from

Comparison is on the 112 parameter bytes of each packed voice, with the 10-byte name field excluded and reported separately.

Against the complete Yamaha DX7 factory set (ROM1A-4B and VRC101A-112B, 1024 voices, 994 unique parameter sets), 40 of the 128 trace back: 23 byte-identical, 9 differing by one to five bytes with a corresponding name, and 8 more within fifteen bytes with a name match.

A control run matters here. Each factory voice compared against the other 993 finds its nearest neighbour at a median distance of 26 bytes. The FM-1 voices sit at 29. So distance alone cannot separate a lifted voice from an unrelated one, and the small-difference band is only meaningful where the names also correspond. That correspondence drops off cleanly with distance: 90 per cent of matches within five bytes have a related name, falling to 15 per cent beyond thirty, which is roughly the rate at which generic words like ORGAN and GUITAR coincide by chance.

The other 88 voices are not official Yamaha material. Against BlackWinny's Dexed_cart_1.0 compilation, though, 126 of the 128 match exactly. The pool used was 3525 banks parsed from 3837 SysEx files, deduplicated to 29615 unique parameter sets, so an exact 112-byte match cannot be an artefact of the collection's internal redundancy.

The two exceptions are GUITAR 4, six bytes from GTRS_01.SYX's GUITAR 1, and GUITAR 5, a single byte from GTRS_A-D.SYX's JAZZ GUITR.

### The naming scheme

The source files themselves explain the names. 119 of the 128 voices appear somewhere in that collection's `!Instruments` category tree, and of the 93 with a category-style name, 90 appear in a folder matching their own category:

| FM-1 slot | Name | Source |
|---|---|---|
| 0 | PIANO 1 | !Instruments/Keyboard/Piano/Electric Piano/EP03.SYX |
| 1 | ORGAN 1 | !Instruments/Keyboard/Organ/Organ1/ORGAN04.SYX |
| 2 | SYN LEAD 1 | !Instruments/Keyboard/Synth/SYNTH_08.SYX |
| 3 | SYN PAD 1 | !Instruments/Keyboard/Synth/Synth Pads/PADS04.SYX |

So the presets were assembled by walking the category folders of a freely circulating DX7 SysEx collection and naming each voice after the folder it was found in, plus a sequential number.

That accounts for the renames. FM-1's GUITAR 3 is DX7 ROM1B's BANJO, and WOODWIND 7 is ROM1B's ACCORDION. Neither name describes the patch; both describe the directory. 24 voices kept their original names and 102 were renamed this way.

It also accounts for the 40 Yamaha factory hits. Those voices are scattered throughout the collection, so picking from category folders picked some up incidentally rather than by design.

Bank 4 kept its original names because slots 96-127 were drawn from `Effects`, `Percussion`, `Ethnic/Latin` and an unsorted `CLANG1.SYX`, where the source names were already specific.

## Oddities

**A name-mangling bug.** Slot 116 is byte-identical to a voice named `BIG  BEN` in EFFECT03.SYX, but the FM-1 calls it `BI   BEN`. The G has become a space. Similar damage shows elsewhere: DX7's STRINGS becomes STRING, and WHAT IF... loses its ellipsis. It only shows up in bank 4, because that is the only bank where original names were kept and so the only place the damage is visible.

**126 voices, not 128.** Slots 115, 119 and 123 hold byte-identical copies of one voice, named SAW EM UP, SAW EM UP2 and SAW EM UP3.

**Inconsistent capitalisation.** Slot 5 is `Organ 2` where every other organ is upper case.

## Files

- `fm1_decode.py` reads a MIDI Monitor `.mmon` capture and writes the four DX7 banks
- `FM-1_factory_bank1-4.syx` the recovered factory set, 4104 bytes each
- `FM-1_factory_128voices_packed.bin` all 128 packed voices, 16384 bytes
- `fm1_compare.py` compares a packed voice dump against reference banks
- `FM-1_provenance.txt` the Yamaha factory trace

A `.mmon` file is an Apple binary property list wrapping an `NSKeyedArchiver` blob. Message bodies are stored without the leading `F0` and trailing `F7`, so a 1190-byte message appears as 1188 bytes.

## Appendix: full provenance table

Source is the file in Dexed_cart_1.0 containing a byte-identical voice. Where a
voice also traces to an official Yamaha cartridge, that is given in the last column.

| Slot | FM-1 name | Source file | Original name | Yamaha cartridge |
|---|---|---|---|---|
| 0 | PIANO 1 | `!Instruments/Keyboard/Piano/Electric Piano/EP03.SYX` v26 | E.PIANO 1 | ROM1A v11 E.PIANO 1 |
| 1 | ORGAN 1 | `!Instruments/Keyboard/Organ/Organ1/ORGAN04.SYX` v12 | E.ORGAN 1 | ROM1A v17 E.ORGAN 1 |
| 2 | SYN LEAD 1 | `!Instruments/Keyboard/Synth/Lead/LEAD02.SYX` v1 | LEADSYN 7 |  |
| 3 | SYN PAD 1 | `!Instruments/Keyboard/Synth/Synth Pads/PADS04.SYX` v5 | PERFECTPAD |  |
| 4 | PIANO 2 | `!Instruments/Keyboard/Piano/Electric Piano/EP04.SYX` v20 | E.PIANO 20 |  |
| 5 | Organ 2 | `!Instruments/Keyboard/Organ/Organ1/ORGAN04.SYX` v29 | E.Organ 2 |  |
| 6 | SYN LEAD 2 | `!Instruments/Keyboard/Synth/Lead/LEAD01.SYX` v25 | LEADSYN 2 |  |
| 7 | SYN PAD 2 | `!Instruments/Keyboard/Synth/Synth Pads/PADS04.SYX` v32 | Voc Pad  1 |  |
| 8 | PIANO3 | `!Instruments/Keyboard/Piano/Electric Piano/EP05.SYX` v23 | E.PIANO 58 | ROM3B v06 E.PIANO 3 |
| 9 | ORGAN 3 | `!Instruments/Keyboard/Organ/Organ1/ORGAN05.SYX` v11 | E.Organ 3 |  |
| 10 | SYN LEAD 3 | `!Instruments/Keyboard/Synth/Lead/LEAD01.SYX` v27 | LEADSYN 3 | ROM4B v12 LEAD GUITR |
| 11 | SYN PAD 3 | `!Instruments/Keyboard/Synth/Synth Pads/PADS04.SYX` v16 | StringPad\ |  |
| 12 | PIANO 4 | `!Instruments/Keyboard/Piano/Electric Piano/EP05.SYX` v8 | E.PIANO 4 | ROM3B v07 E.PIANO 4 |
| 13 | ORGAN 4 | `!Instruments/Keyboard/Organ/Organ1/ORGAN05.SYX` v23 | E.ORGAN 40 |  |
| 14 | SYN LEAD 4 | `!Instruments/Keyboard/Synth/Lead/LEAD01.SYX` v28 | LEADSYN 4 |  |
| 15 | SYN PAD 4 | `!Instruments/Keyboard/Synth/Synth Pads/PADS04.SYX` v15 | SPACE PAD |  |
| 16 | PIANO 5 | `!Instruments/Keyboard/Piano/Electric Piano/E_PIANO1.SYX` v10 | E.PIANO 5A | ROM1A v11 E.PIANO 1 |
| 17 | ORGAN 5 | `!Instruments/Keyboard/Organ/Organ1/ORGAN05.SYX` v1 | E.ORGAN 2 | ROM3B v13 E.ORGAN 2 |
| 18 | SYN LEAD 5 | `!Instruments/Keyboard/Synth/Lead/LEAD01.SYX` v11 | FAT LEAD |  |
| 19 | SYN PAD 5 | `!Instruments/Keyboard/Synth/Synth Pads/PADS04.SYX` v12 | Slow3D Pad |  |
| 20 | PIANO 6 | `!Instruments/Keyboard/Piano/Electric Piano/EP04.SYX` v4 | E.PIANO 13 |  |
| 21 | ORGAN 6 | `!Instruments/Keyboard/Organ/Organ1/ORGAN05.SYX` v20 | E.ORGAN 39 | ROM3B v14 E.ORGAN 3 |
| 22 | SYN LEAD 6 | `!Instruments/Keyboard/Synth/Lead/LEAD01.SYX` v31 | LEADSYN 5 |  |
| 23 | SYN PAD 6 | `!Instruments/Keyboard/Synth/Synth Pads/PADS03.SYX` v14 | MODERN PAD |  |
| 24 | PIANO 7 | `!Instruments/Keyboard/Piano/Electric Piano/EP05.SYX` v27 | E.PIANO 7 | VRC101A v09 E.PIANO  3 |
| 25 | ORGAN 7 | `!Instruments/Keyboard/Organ/Organ1/ORGAN05.SYX` v32 | E.ORGAN 60 | ROM1B v15 E.ORGAN 4 |
| 26 | SYN LEAD 7 | `!Instruments/Keyboard/Synth/Lead/LEAD01.SYX` v32 | LEADSYN 6 |  |
| 27 | SYN PAD 7 | `!Instruments/Effects/EFFECTS8.SYX` v6 | 'JudgemtHM |  |
| 28 | PIANO 8 | `!Instruments/Keyboard/Piano/Electric Piano/EP05.SYX` v28 | E.PIANO 7 | VRC101A v10 E.PIANO  4 |
| 29 | ORGAN 8 | `!Instruments/Keyboard/Organ/Organ1/ORGAN05.SYX` v29 | E.ORGAN 52 |  |
| 30 | SYN LEAD 8 | `!Instruments/Keyboard/Synth/Lead/LEAD02.SYX` v4 | METAL LEAD |  |
| 31 | SYN PAD 8 | `!Instruments/Keyboard/Synth/Synth Pads/PADS03.SYX` v17 | MOVIE PAD |  |
| 32 | GUITAR 1 | `!Instruments/Plucked/Guitar/GTRS_A-D.SYX` v3 | BLUES GUIT |  |
| 33 | DS GUITAR1 | `!Instruments/Plucked/Guitar/Guitar2/GUITAR02.SYX` v14 | DIST.GUIT | VRC109A v22 DIST.GUIT |
| 34 | BASS 1 | `!Instruments/Plucked/Bass/Bass1/BASS001.SYX` v2 | *Bass-Synt |  |
| 35 | SYN BASS1 | `!Instruments/Plucked/Bass/Bass1/BASS007.SYX` v4 | DENTIST |  |
| 36 | GUITAR 2 | `!Instruments/Plucked/Guitar/GTRS_N-R.SYX` v1 | NYLON G1TR |  |
| 37 | DS GUITAR2 | `!Instruments/Plucked/Guitar/GTRS_EL.SYX` v1 | DS.GUITAR1 |  |
| 38 | BASS 2 | `!Instruments/Keyboard/Synth/Synth08/SYST_BB.SYX` v14 | *DISCOBASS |  |
| 39 | SYN BASS2 | `!Instruments/Plucked/Bass/Bass1/BASS007.SYX` v8 | DigiBass \ |  |
| 40 | GUITAR 3 | `!Instruments/Keyboard/Piano/Piano4/piano clav harp pipes gtr.syx` v28 | BANJO | ROM1B v28 BANJO |
| 41 | DS GUITAR3 | `!Instruments/Keyboard/Synth/Synth06/syndec2.syx` v31 | DS.GUITAR2 |  |
| 42 | BASS 3 | `!Instruments/Plucked/Bass/Bass1/BASS001.SYX` v20 | Ac.Bass*5 | ROM1B v32 BASS    4 |
| 43 | SYN BASS3 | `!Instruments/Misc/Dx111.syx` v17 | DOLBY BASS |  |
| 44 | GUITAR 4 | `!Instruments/Plucked/Guitar/GTRS_01.SYX (differs by 6)` v5 | GUITAR  1 |  |
| 45 | DS GUITAR4 | `!Instruments/Plucked/Guitar/GTRS_D.SYX` v3 | E.GUITAR 2 | VRC101A v26 E.GUITAR 2 |
| 46 | BASS 4 | `!Instruments/Plucked/Bass/Bass1/BASS001.SYX` v9 | *Walk Bass |  |
| 47 | SYN BASS4 | `!Instruments/Misc/MISC_21.SYX` v32 | DONT FRET. |  |
| 48 | GUITAR 5 | `!Instruments/Plucked/Guitar/GTRS_A-D.SYX (differs by 1)` v12 | JAZZ GUITR | ROM3A v15 JAZZ GUIT1 |
| 49 | DS GUITAR5 | `!Instruments/Plucked/Guitar/GTRS_EL.SYX` v13 | PWR-GUITAR |  |
| 50 | BASS 5 | `!Instruments/Keyboard/Synth/Synth08/SYST_BB.SYX` v12 | *Funkbass |  |
| 51 | SYN BASS5 | `!Instruments/Keyboard/Piano/PIANO_13.SYX` v17 | DX9. 8 |  |
| 52 | GUITAR 6 | `!Instruments/Misc/Bank0047.syx` v24 | FOLK GUIT | ROM3B v25 FOLK GUIT |
| 53 | DS GUITAR6 | `!Instruments/Keyboard/Synth/dirty/SYDRTY01.SYX` v6 | HEAVYMETL2 | ROM3A v21 HEAVYMETAL |
| 54 | BASS 6 | `!Instruments/Plucked/Bass/Bass1/BASS001.SYX` v7 | *Slap Bass |  |
| 55 | SYN BASS6 | `!Instruments/Plucked/Bass/Bass1/BASS007.SYX` v24 | E BASS 4 | VRC106B v04 SYN.BASS10 |
| 56 | GUITAR 7 | `!Instruments/Keyboard/Piano/Piano4/piano clav harp pipes gtr.syx` v23 | GUITAR  3 | ROM1B v23 GUITAR  3 |
| 57 | DS GUITAR7 | `!Instruments/Plucked/Guitar/GTRS_L-N.SYX` v4 | LEAD-GUITR | ROM4B v12 LEAD GUITR |
| 58 | BASS 7 | `!Instruments/Plucked/Bass/Bass1/BASS007.SYX` v27 | E BASS 5 |  |
| 59 | SYN BASS7 | `!Instruments/Plucked/Bass/Bass1/BASS007.SYX` v28 | E BASS 6 |  |
| 60 | GUITAR 8 | `!Instruments/Plucked/Guitar/Guitar2/GUITAR09.SYX` v24 | Guit el 24 |  |
| 61 | DS GUITAR8 | `!Instruments/Plucked/Guitar/GTRS_D.SYX` v16 | FUZZ GUIT1 |  |
| 62 | BASS 8 | `!Instruments/Plucked/Bass/Bass1/BASS007.SYX` v31 | E BASS 85 |  |
| 63 | SYN BASS8 | `!Instruments/Plucked/Bass/Bass1/BASS007.SYX` v32 | E BASS IC |  |
| 64 | BRASS 1 | `!Instruments/Brass/Brass1/BRASS-01.SYX` v1 | *Bay.Brass |  |
| 65 | WOODWIND 1 | `!Instruments/Brass/Brass4/brass wind flutes.syx` v27 | *Bassoon 1 | VRC102A v17 BASSOON  3 |
| 66 | STRING 1 | `!Instruments/Percussion/Bells/BELLTEL.SYX` v15 | WARM STRNG |  |
| 67 | VOICE 1 | `!Instruments/Misc/MISC_06.SYX` v26 | *TheRiddle |  |
| 68 | BRASS 2 | `!Instruments/Brass/Brass1/BRASS-01.SYX` v2 | *Bellbrass |  |
| 69 | WOODWIND 2 | `!Instruments/Brass/Brass4/brass wind flutes.syx` v28 | *Bassoon 2 | VRC102A v15 BASSOON  1 |
| 70 | STRING 2 | `!Instruments/Orchestra/ORCHESTR.SYX` v5 | STRG ENS 1 | ROM3A v03 STRG ENS 1 |
| 71 | VOICE 2 | `!Instruments/Voice/Voice2/VOICE01.SYX` v2 | *Vox Human |  |
| 72 | BRASS 3 | `!Instruments/Brass/Brass1/BRASS-01.SYX` v3 | *Brass 5+ |  |
| 73 | WOODWIND 3 | `!Instruments/Brass/Brass4/brass wind flutes.syx` v17 | *Harmonica |  |
| 74 | STRING 3 | `!Instruments/Strings/Strings1/STRING1.SYX` v11 | NSTRNG 425 |  |
| 75 | VOICE 3 | `!Instruments/Voice/Voice2/VOICE01.SYX` v14 | COSMVOICE |  |
| 76 | BRASS 4 | `!Instruments/Brass/Brass1/BRASS-01.SYX` v4 | *Fl.Horn |  |
| 77 | WOODWIND 4 | `!Instruments/Brass/Brass4/brass wind flutes.syx` v25 | *Oboe | VRC102A v09 OBOE     2 |
| 78 | STRING 4 | `!Instruments/Strings/Strings1/STRING1.SYX` v4 | HI STR.ENS | ROM1A v05 STRINGS 2 |
| 79 | VOICE 4 | `!Instruments/Misc/DX72MR2.SYX` v22 | FL.CLOUD A |  |
| 80 | BRASS 5 | `!Instruments/Brass/Brass1/BRASS-01.SYX` v5 | *Horn 2 | VRC102A v23 HORN     2 |
| 81 | WOODWIND 5 | `!Instruments/Woodwind/WIND--01.SYX` v10 | 9accordian |  |
| 82 | STRING 5 | `!Instruments/Misc/Dx7_0628.syx` v19 | Orchestra |  |
| 83 | VOICE 5 | `!Instruments/Percussion/Drums/Drmoct.syx` v1 | 99  VOICES |  |
| 84 | BRASS 6 | `!Instruments/Brass/Brass1/BRASS-01.SYX` v6 | *Keybrass |  |
| 85 | WOODWIND 6 | `!Instruments/Woodwind/FLUTE01.SYX` v2 | *Panfloete |  |
| 86 | STRING 6 | `!Instruments/Misc/Bank0043.syx` v13 | STRG ENS 2 | ROM4A v14 STRG ENS 2 |
| 87 | VOICE 6 | `!Instruments/Misc/MORTEGA.SYX` v29 | ANGELS AAH | ROM2A v21 VOICE   3 |
| 88 | BRASS 7 | `!Instruments/Brass/Brass1/BRASS-01.SYX` v7 | *Pia-Brass |  |
| 89 | WOODWIND 7 | `!Instruments/Accordion/ACCORD01.SYX` v1 | ACCORDION | ROM1B v21 ACCORDION |
| 90 | STRING 7 | `!Instruments/Strings/Strings1/STRING1.SYX` v7 | FAT ENSEM |  |
| 91 | VOICE 7 | `!Instruments/Misc/TEXTURES.SYX` v10 | ANGEL A -- |  |
| 92 | BRASS 8 | `!Instruments/Brass/Brass1/BRASS-01.SYX` v8 | *Trombone |  |
| 93 | WOODWIND 8 | `!Instruments/Keyboard/Synth/Synth01/SYNTH002.SYX` v28 | ?Flooty |  |
| 94 | STRING 8 | `!Instruments/Misc/d quatro a.syx` v2 | HI STRINGS |  |
| 95 | VOICE 8 | `!Instruments/Misc/POWERPLY.SYX` v10 | ANGEL B -- |  |
| 96 | BOWOAN | `!Instruments/Percussion/Perc.SYX` v1 | BOWOAN |  |
| 97 | BDWHOCARES | `!Instruments/Percussion/PERCUS_4.SYX` v19 | BDWHOCARES |  |
| 98 | BLOCK | `!Instruments/Ethnic/Latin/LATIN.SYX` v6 | BLOCK | ROM2A v30 BLOCK |
| 99 | WAVES | `!Instruments/Effects/Effect-1.syx` v32 | WAVES |  |
| 100 | FROGBELL | `!Instruments/Misc/DX148.SYX` v10 | FROGBELL |  |
| 101 | ELECT.GONG | `!Instruments/Misc/MISC_19.SYX` v27 | ELECT.GONG |  |
| 102 | TORIMTORA2 | `!Instruments/Ethnic/Latin/LATIN.SYX` v7 | TORIMTORA2 |  |
| 103 | MONO M | `!Instruments/Effects/WEIRD1.SYX` v10 | MONO M |  |
| 104 | TIBET | `!Instruments/Keyboard/Synth/Synth01/SYNTH048.SYX` v18 | TIBET |  |
| 105 | LOG DRUM | `!Instruments/Misc/Bank0043.syx` v29 | LOG DRUM | ROM4A v30 LOG DRUM |
| 106 | COWBELL | `!Instruments/Misc/Bank0043.syx` v26 | COWBELL | ROM2A v29 COW BELL |
| 107 | MONO Z | `!Instruments/Effects/WEIRD1.SYX` v11 | MONO Z |  |
| 108 | FINGERCYM | `!Instruments/Misc/DX148.SYX` v12 | FINGERCYM |  |
| 109 | TIMPANI | `!Instruments/Misc/Dx114.syx` v23 | TIMPANI | ROM3A v20 TIMPANI |
| 110 | TAMBOURINE | `!Instruments/Misc/Dx103.syx` v23 | TAMBOURINE | VRC104B v05 TAMBLN.  1 |
| 111 | DESCENT | `!Instruments/Effects/EFFECT04.SYX` v26 | DESCENT | ROM2B v28 DESCENT |
| 112 | CLANG BELL | `!Instruments/Percussion/Perc.SYX` v5 | CLANG BELL |  |
| 113 | STEEL DRUM | `!Instruments/Percussion/PERCUS04.SYX` v5 | STEEL DRUM | ROM3A v22 STEEL DRUM |
| 114 | CONGA | `Aminet/165.syx` v27 | CONGA |  |
| 115 | SAW EM UP | `!Instruments/Effects/Effect-1.syx` v15 | SAW EM UP |  |
| 116 | BI   BEN | `!Instruments/Effects/EFFECT03.SYX` v1 | BIG  BEN | VRC105B v18 BIG BEN |
| 117 | KALIMBA | `!Instruments/Misc/DX149.SYX` v20 | -KALIMBA- |  |
| 118 | GAMALONG | `!Instruments/Ethnic/Ethnic.syx` v20 | GAMALONG |  |
| 119 | SAW EM UP2 | `!Instruments/Effects/Effect-1.syx` v15 | SAW EM UP |  |
| 120 | TUB BELLS | `!Instruments/Keyboard/Organ/Dxorgans.syx` v11 | TUB BELLS | ROM1A v26 TUB BELLS |
| 121 | BRUSHES | `!Instruments/Effects/EFFECT03.SYX` v19 | -BRUSHES- |  |
| 122 | TOM TOMS | `!Instruments/Ethnic/Latin/LATIN.SYX` v25 | TOM TOMS |  |
| 123 | SAW EM UP3 | `!Instruments/Effects/Effect-1.syx` v15 | SAW EM UP |  |
| 124 | ECHO | `!Instruments/Percussion/Perc.SYX` v10 | ECHO------ |  |
| 125 | TIMBALI | `!Instruments/Misc/Dx114.syx` v1 | TIMBALI 1 | VRC104A v16 TIMBALES 2 |
| 126 | PERCUSSION | `!Instruments/Ethnic/Latin/LATIN.SYX` v27 | PERCUSSION |  |
| 127 | WHAT IF | `!Instruments/Effects/Effect-1.syx` v11 | WHAT IF... |  |
