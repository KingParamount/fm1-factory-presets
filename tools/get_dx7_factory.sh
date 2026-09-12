#!/bin/sh
# Fetch every Yamaha DX7 factory cartridge (ROM1A-4B and VRC101A-112B) and
# concatenate them into a single .syx stream for analysis.
#
# Source: https://yamahablackboxes.com/collection/yamaha-dx7-synthesizer/patches/
# (the same source MiniDexed's getsysex.sh uses)
#
# Produces:  dx7_factory_all.syx   - all banks, back to back
#            banks/                - the individual files, correctly named

set -e
mkdir -p banks
cd banks

ROMBASE="https://yamahablackboxes.com/patches/dx7/factory"
VRCBASE="https://yamahablackboxes.com/patches/dx7/vrc"

for n in 1 2 3 4; do
  for s in a b; do
    f="rom${n}${s}.syx"
    [ -s "$f" ] || curl -fsS -o "$f" "${ROMBASE}/${f}" || echo "missed ${f}"
  done
done

for n in 101 102 103 104 105 106 107 108 109 110 111 112; do
  for s in a b; do
    f="vrc${n}${s}.syx"
    [ -s "$f" ] || curl -fsS -o "$f" "${VRCBASE}/${f}" || echo "missed ${f}"
  done
done

cd ..
cat banks/rom*.syx banks/vrc*.syx > dx7_factory_all.syx

echo
echo "banks fetched: $(ls banks/*.syx | wc -l)"
echo "combined size: $(wc -c < dx7_factory_all.syx) bytes"
echo "expected 4104 per bank, so $(( $(wc -c < dx7_factory_all.syx) / 4104 )) banks of 32 voices"
