#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/lib.sh"

REFIND_DIR="${REFIND_DIR:-/boot/efi/EFI/refind}"
CONF="$REFIND_DIR/refind.conf"
THEMES="$REFIND_DIR/themes"

usage() {
  cat <<EOF
prettyboot - rEFInd boot theme manager

Usage (run with sudo on a real system):
  prettyboot.sh list                 list themes (* active, ✓ valid, ✗ broken)
  prettyboot.sh use <theme>          activate a theme
  prettyboot.sh next                 switch to the next valid theme
  prettyboot.sh timeout <secs|off>   set boot menu timeout (off = wait forever)
  prettyboot.sh reset                remove prettyboot's settings (plain rEFInd)
EOF
}

cmd="${1:-}"
case "$cmd" in
  list)
    active="$(pb_active_theme "$CONF")"
    for name in $(pb_list_theme_names "$THEMES"); do
      if pb_validate_theme "$THEMES" "$name" 2>/dev/null; then mark="✓"; else mark="✗"; fi
      if [ "$name" = "$active" ]; then cur="*"; else cur=" "; fi
      printf "%s %s %s\n" "$cur" "$mark" "$name"
    done
    ;;
  use)
    name="${2:?usage: use <theme>}"
    pb_validate_theme "$THEMES" "$name" || exit 1
    t="$(pb_block_get "$CONF" timeout)"; t="${t:-10}"
    pb_block_write "$CONF" "$t" "themes/$name/theme.conf"
    echo "Active theme: $name"
    ;;
  next)
    active="$(pb_active_theme "$CONF")"
    valid=()
    for name in $(pb_list_theme_names "$THEMES"); do
      pb_validate_theme "$THEMES" "$name" 2>/dev/null && valid+=("$name")
    done
    [ "${#valid[@]}" -gt 0 ] || { echo "no valid themes found" >&2; exit 1; }
    idx=0
    for i in "${!valid[@]}"; do
      [ "${valid[$i]}" = "$active" ] && idx=$(( (i + 1) % ${#valid[@]} ))
    done
    exec "$0" use "${valid[$idx]}"
    ;;
  timeout)
    val="${2:?usage: timeout <secs|off>}"
    case "$val" in
      off) val=0 ;;
      ''|*[!0-9]*) echo "timeout must be a number or 'off'" >&2; exit 1 ;;
    esac
    inc="$(pb_block_get "$CONF" include)"
    pb_block_write "$CONF" "$val" "$inc"
    echo "Timeout: $val"
    ;;
  reset)
    pb_block_remove "$CONF"
    echo "prettyboot settings removed; plain rEFInd restored"
    ;;
  ''|-h|--help|help)
    usage
    ;;
  *)
    usage; exit 1
    ;;
esac
