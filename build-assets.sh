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

# --- selection highlights ---
# sizes per rEFInd docs: selection_big = 9/8 of 128 icon (144), small = 4/3 of 48 (64)
convert -size 144x144 xc:none -fill 'rgba(255,255,255,0.16)' \
  -draw 'roundrectangle 6,6,138,138,26,26' "$md/selection_big.png"
convert -size 64x64 xc:none -fill 'rgba(255,255,255,0.16)' \
  -draw 'roundrectangle 4,4,60,60,14,14' "$md/selection_small.png"
convert -size 144x144 xc:none -fill 'rgba(0,0,0,0.14)' \
  -draw 'roundrectangle 6,6,138,138,26,26' "$ml/selection_big.png"
convert -size 64x64 xc:none -fill 'rgba(0,0,0,0.14)' \
  -draw 'roundrectangle 4,4,60,60,14,14' "$ml/selection_small.png"

# --- icons: latest (2026) official logos, shared by both themes ---
# Windows 11 four-square (2021, still current); Ubuntu 2022 Circle of Friends on
# an orange squircle. SVGs inlined so this script stays self-contained.
tmp="$(mktemp -d)"
cat > "$tmp/os_win.svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4875 4875"><path fill="#0078d4" d="M0 0h2311v2310H0zm2564 0h2311v2310H2564zM0 2564h2311v2311H0zm2564 0h2311v2311H2564"/></svg>
SVG
cat > "$tmp/os_ubuntu.svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">
  <rect width="1024" height="1024" rx="230" fill="#e9500e"/>
  <g fill="#fff" transform="translate(93.2,-352.8) scale(0.803)">
    <circle cx="226.58835" cy="1056.07411" r="109.02696"/>
    <circle cx="680.64509" cy="817.00695" r="109.02696"/>
    <circle cx="656.08182" cy="1337.26719" r="109.02696"/>
    <path d="M472.48179,1336.66575a265.525,265.525,0,0,1-181.07121-138.09821,156.94811,156.94811,0,0,1-93.21911,11.45831,354.9352,354.9352,0,0,0,255.53721,214.16456,359.21054,359.21054,0,0,0,77.41948,7.967,156.00315,156.00315,0,0,1-31.92236-91.15471C490.24607,1340.00523,481.27719,1338.548,472.48179,1336.66575Z"/>
    <path d="M807.7978,1297.22089A356.70056,356.70056,0,0,0,825.67268,878.702a157.14405,157.14405,0,0,1-61.30976,71.80309,267.293,267.293,0,0,1-8.73685,265.48842A156.34662,156.34662,0,0,1,807.7978,1297.22089Z"/>
    <path d="M218.17628,899.71905q4.1505-.2277,8.30533-.22553A157.3464,157.3464,0,0,1,309.164,923.039,265.90648,265.90648,0,0,1,523.2722,808.52964a158.08773,158.08773,0,0,1,33.076-88.42024C419.24532,709.25176,286.02405,780.001,218.17628,899.71905Z"/>
  </g>
</svg>
SVG
for d in "$md" "$ml"; do
  rsvg-convert -w 256 -h 256 "$tmp/os_ubuntu.svg" -o "$d/icons/os_ubuntu.png"
  cp "$d/icons/os_ubuntu.png" "$d/icons/os_linux.png"   # linux fallback = ubuntu badge
  rsvg-convert -w 256 -h 256 "$tmp/os_win.svg"    -o "$d/icons/os_win.png"
  # rEFInd tags the modern Windows Boot Manager as "win8" and looks for os_win8
  # FIRST; without it, it falls back to its built-in tilted Win8 logo. Provide it.
  cp "$d/icons/os_win.png" "$d/icons/os_win8.png"
done
rm -rf "$tmp"

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

echo "Generated themes: mac-dark, mac-light"
