#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/lib.sh"

REFIND_DIR="${REFIND_DIR:-/boot/efi/EFI/refind}"
SRC_THEMES="${SRC_THEMES:-$here/themes}"

# 1. Ensure rEFInd is installed (only if its dir does not already exist).
if [ ! -d "$REFIND_DIR" ]; then
  if command -v apt-get >/dev/null 2>&1; then
    echo "Installing rEFInd via apt-get..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y refind
  else
    echo "rEFInd not found and apt-get unavailable. Install rEFInd manually, then re-run." >&2
    exit 1
  fi
fi

# 2. Verify rEFInd config exists.
[ -d "$REFIND_DIR" ] || { echo "rEFInd dir not found at $REFIND_DIR" >&2; exit 1; }
CONF="$REFIND_DIR/refind.conf"
[ -f "$CONF" ] || { echo "refind.conf not found at $CONF" >&2; exit 1; }

# 3. Back up the original config once.
[ -f "$CONF.prettyboot.bak" ] || cp "$CONF" "$CONF.prettyboot.bak"

# 4. Deploy bundled themes.
pb_deploy_themes "$SRC_THEMES" "$REFIND_DIR/themes"

# 5. Set defaults: 10s timeout, mac-dark active.
pb_block_write "$CONF" 10 themes/mac-dark/theme.conf

echo "prettyboot installed. Default theme: mac-dark, timeout 10s."
echo "Reboot to see it. Switch anytime:"
echo "  sudo $here/prettyboot.sh list"
echo "  sudo $here/prettyboot.sh use mac-light"
