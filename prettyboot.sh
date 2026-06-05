#!/usr/bin/env bash
set -euo pipefail
# resolve symlinks so `prettyboot` in PATH still finds lib.sh next to the real script
here="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
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

  prettyboot.sh                      (no command) open the interactive menu
EOF
}

# Interactive menu shown when prettyboot is run with no command.
menu() {
  local active t choice
  while true; do
    active="$(pb_active_theme "$CONF")"
    t="$(pb_block_get "$CONF" timeout)"
    case "$t" in "") t="(not set)" ;; 0) t="off (waits for you)" ;; *) t="${t}s" ;; esac
    printf '\n=== prettyboot ===\n'
    printf 'Active theme : %s\n'   "${active:-none}"
    printf 'Timeout      : %s\n\n' "$t"
    printf '  1) Choose theme\n'
    printf '  2) Set timeout\n'
    printf '  3) Reset to plain rEFInd\n'
    printf '  4) Quit\n'
    printf 'Select: '
    read -r choice || break
    case "$choice" in
      1) menu_choose_theme ;;
      2) menu_set_timeout ;;
      3) "$0" reset || true ;;
      4|q|Q|quit|exit) break ;;
      *) echo "Invalid choice." ;;
    esac
  done
}

menu_choose_theme() {
  local names=() n i sel idx mark
  for n in $(pb_list_theme_names "$THEMES"); do names+=("$n"); done
  if [ "${#names[@]}" -eq 0 ]; then echo "No themes found in $THEMES"; return; fi
  echo
  for i in "${!names[@]}"; do
    if pb_validate_theme "$THEMES" "${names[$i]}" 2>/dev/null; then mark="✓"; else mark="✗"; fi
    printf '  %d) %s %s\n' "$((i + 1))" "$mark" "${names[$i]}"
  done
  printf 'Theme number (blank to cancel): '
  read -r sel || return
  case "$sel" in ''|*[!0-9]*) echo "Cancelled."; return ;; esac
  idx=$((sel - 1))
  if [ "$idx" -lt 0 ] || [ "$idx" -ge "${#names[@]}" ]; then echo "Out of range."; return; fi
  "$0" use "${names[$idx]}" || true
}

menu_set_timeout() {
  local val
  printf "Timeout seconds, or 'off' to wait forever (blank to cancel): "
  read -r val || return
  [ -n "$val" ] || { echo "Cancelled."; return; }
  "$0" timeout "$val" || true
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
  ''|menu)
    menu
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage; exit 1
    ;;
esac
