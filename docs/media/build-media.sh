#!/usr/bin/env bash
# build-media.sh - regenerate the README media in docs/media/.
# BUILD-TIME ONLY. End users never run this. Requires imagemagick; cli-demo.gif
# additionally needs `agg` (https://github.com/asciinema/agg). gui-themes.png
# is a hand-captured screenshot of the running GUI and is not regenerated here.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../.." && pwd)"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

# --- boot-menu stills + GIF frames via the GUI's own headless renderer,
# so README previews stay pixel-identical to what the app (and rEFInd) shows ---
render() { # <theme-dir> <out.png> <w> <h> <selected>
  PYTHONPATH="$root/gui" python3 - "$@" <<'EOF'
import sys
from prettyboot_gui.preview import render_png
theme, out, w, h, sel = sys.argv[1:6]
render_png(theme, out, int(w), int(h), selected=int(sel))
EOF
}

render "$root/themes/mac-dark"  "$here/preview-mac-dark.png"  1024 768 0
render "$root/themes/mac-light" "$here/preview-mac-light.png" 1024 768 0

for t in dark light; do
  for s in 0 1; do render "$root/themes/mac-$t" "$tmp/$t-$s.png" 800 600 "$s"; done
done
magick -loop 0 \
  -delay 170 "$tmp/dark-0.png"  -delay 90 "$tmp/dark-1.png"  -delay 90 "$tmp/dark-0.png" \
  -delay 170 "$tmp/light-0.png" -delay 90 "$tmp/light-1.png" -delay 90 "$tmp/light-0.png" \
  -layers optimize "$here/boot-menu.gif"

# --- CLI demo: synthesized asciinema cast (real captured outputs) -> GIF ---
if command -v agg >/dev/null 2>&1; then
  (cd "$tmp" && python3 "$here/make-cast.py")
  agg --theme dracula --font-size 18 --line-height 1.5 \
    "$tmp/cli-demo.cast" "$here/cli-demo.gif"
else
  echo "agg not found — skipping cli-demo.gif" >&2
fi
