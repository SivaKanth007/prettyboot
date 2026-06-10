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
# mac-dark: deep near-black with a subtle purple core. Kept dark on purpose so
# rEFInd's auto text-color picks WHITE (it has no text-color setting).
convert -size ${W}x${H} radial-gradient:'#1c1430'-'#020103' "$md/background.png"
# mac-light: soft, clean pastel gradient (cream -> soft blue). No baked panel;
# rEFInd draws the per-icon selection highlight. Kept light so auto text = black.
convert -size ${W}x${H} gradient:'#fde7d6'-'#c7dbf0' "$ml/background.png"

# --- selection highlights: liquid-glass tiles from assets/selection_*.svg ---
# sizes per rEFInd docs: selection_big = 9/8 of 128 icon (144), small = 4/3 of 48 (64)
rsvg-convert -w 144 -h 144 "$here/assets/selection_dark.svg"  -o "$md/selection_big.png"
rsvg-convert -w 64  -h 64  "$here/assets/selection_dark.svg"  -o "$md/selection_small.png"
rsvg-convert -w 144 -h 144 "$here/assets/selection_light.svg" -o "$ml/selection_big.png"
rsvg-convert -w 64  -h 64  "$here/assets/selection_light.svg" -o "$ml/selection_small.png"

# --- icons: glass set rendered from assets/*.svg (Microsoft-Authenticator-style
# glassmorphism: gradient base, diagonal sheen, edge highlight, soft shadow) ---
for d in "$md" "$ml"; do
  rsvg-convert -w 256 -h 256 "$here/assets/os_ubuntu.svg" -o "$d/icons/os_ubuntu.png"
  cp "$d/icons/os_ubuntu.png" "$d/icons/os_linux.png"   # linux fallback = ubuntu badge
  rsvg-convert -w 256 -h 256 "$here/assets/os_win.svg"    -o "$d/icons/os_win.png"
  # rEFInd tags the modern Windows Boot Manager as "win8" and looks for os_win8
  # FIRST; without it, it falls back to its built-in tilted Win8 logo. Provide it.
  cp "$d/icons/os_win.png" "$d/icons/os_win8.png"
done
# --- desktop app icon (referenced by gui/prettyboot.desktop Icon=prettyboot) ---
rsvg-convert -w 256 -h 256 "$here/assets/prettyboot.svg" -o "$here/assets/prettyboot.png"

# --- fonts ---
# No custom font: rEFInd has no text-color option (it auto-picks black/white from
# the background brightness, ignoring a font PNG's color), so a custom font only
# changes shape/size, not readability. We use rEFInd's built-in 14pt font and
# instead control readability via background brightness (dark bg => white text).

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
# keep OS name labels visible; hide only the key hints, scroll arrows and the
# OS "badge" overlay for a cleaner look. Boot entries are left untouched.
hideui hints,arrows,badges
EOF
}
write_conf "$md" mac-dark
write_conf "$ml" mac-light

# Dark theme only: launch Windows in graphics mode. Because the dark background is
# near-black, the brief handoff screen stays black (clean) instead of showing the
# verbose text-mode "Starting bootmgfw.efi" message. (On the light theme this would
# leave a white screen, so it is intentionally NOT added there.)
echo "use_graphics_for +,windows" >> "$md/theme.conf"

echo "Generated themes: mac-dark, mac-light"
