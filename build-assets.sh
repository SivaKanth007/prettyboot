#!/usr/bin/env bash
# build-assets.sh - regenerate the mac-dark and mac-light theme PNGs.
# BUILD-TIME ONLY. End users never run this. Requires imagemagick + librsvg2-bin.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
W=1920; H=1080
md="$here/themes/mac-dark"
ml="$here/themes/mac-light"
mkdir -p "$md/icons" "$ml/icons"

# --- backgrounds ---
# mac-dark: Sonoma-style radial purple -> near-black
convert -size ${W}x${H} radial-gradient:'#3a2a5c'-'#08060f' "$md/background.png"
# mac-light: Big Sur-style color gradient + baked frosted panel (no live blur at boot)
convert -size ${W}x${H} gradient:'#ff9a8b'-'#8fd3f4' \
  -fill 'rgba(255,255,255,0.35)' -draw 'roundrectangle 560,400,1360,680,28,28' \
  "$ml/background.png"

# --- selection highlights ---
convert -size 160x160 xc:none -fill 'rgba(255,255,255,0.16)' \
  -draw 'roundrectangle 6,6,154,154,28,28' "$md/selection_big.png"
convert -size 64x64 xc:none -fill 'rgba(255,255,255,0.16)' \
  -draw 'roundrectangle 4,4,60,60,14,14' "$md/selection_small.png"
convert -size 160x160 xc:none -fill 'rgba(0,0,0,0.18)' \
  -draw 'roundrectangle 6,6,154,154,28,28' "$ml/selection_big.png"
convert -size 64x64 xc:none -fill 'rgba(0,0,0,0.18)' \
  -draw 'roundrectangle 4,4,60,60,14,14' "$ml/selection_small.png"

# --- icons (shared art for both themes) ---
tmp="$(mktemp -d)"
cat > "$tmp/os_linux.svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle cx="50" cy="50" r="46" fill="#E95420"/>
  <g fill="#fff">
    <circle cx="50" cy="22" r="8"/><circle cx="26" cy="64" r="8"/><circle cx="74" cy="64" r="8"/>
  </g>
  <g stroke="#fff" stroke-width="6" fill="none">
    <path d="M50 30 A20 20 0 0 1 67 58"/>
    <path d="M33 58 A20 20 0 0 1 50 30"/>
    <path d="M67 58 A20 20 0 0 1 33 58"/>
  </g>
</svg>
SVG
cat > "$tmp/os_win.svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <g fill="#3a9bdc">
    <rect x="14" y="14" width="33" height="33" rx="2"/>
    <rect x="53" y="14" width="33" height="33" rx="2"/>
    <rect x="14" y="53" width="33" height="33" rx="2"/>
    <rect x="53" y="53" width="33" height="33" rx="2"/>
  </g>
</svg>
SVG
for d in "$md" "$ml"; do
  rsvg-convert -w 128 -h 128 "$tmp/os_linux.svg" -o "$d/icons/os_linux.png"
  rsvg-convert -w 128 -h 128 "$tmp/os_win.svg"   -o "$d/icons/os_win.png"
done
rm -rf "$tmp"

# --- theme.conf for each theme ---
write_conf() {  # <dir> <name>
  cat > "$1/theme.conf" <<EOF
# prettyboot theme: $2
banner themes/$2/background.png
banner_scale fillscreen
icons_dir themes/$2/icons
selection_big themes/$2/selection_big.png
selection_small themes/$2/selection_small.png
big_icon_size 128
small_icon_size 48
EOF
}
write_conf "$md" mac-dark
write_conf "$ml" mac-light

echo "Generated themes: mac-dark, mac-light"
