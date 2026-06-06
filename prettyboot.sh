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

# Simple numbered menu — fallback when stdin/stdout aren't a terminal (pipes/tests).
menu_simple() {
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

# --- arrow-key TUI (used when stdin/stdout are a terminal) ---

REPLY_INDEX=0
pb_pause() { printf '\nPress any key to continue...'; read -rsn1 _ || true; }

# tui_select <title> <option>...  -> sets REPLY_INDEX and returns 0; returns 1 if cancelled.
tui_select() {
  local title="$1"; shift
  local options=("$@") n=$# cur=0 key key2 i
  printf '\033[?25l'                                  # hide cursor
  while true; do
    printf '\033[2J\033[H'                            # clear screen, home
    printf '%s\n\n' "$title"
    for i in "${!options[@]}"; do
      if [ "$i" -eq "$cur" ]; then
        printf '  \033[7m %s \033[0m\n' "${options[$i]}"   # highlighted row
      else
        printf '    %s\n' "${options[$i]}"
      fi
    done
    printf '\n(\342\206\221/\342\206\223 move, Enter select, q back)'
    IFS= read -rsn1 key || { printf '\033[?25h\n'; return 1; }
    case "$key" in
      $'\033')                                        # escape sequence
        IFS= read -rsn2 -t 0.05 key2 || key2=""
        case "$key2" in
          '[A') cur=$(( (cur - 1 + n) % n )) ;;       # up
          '[B') cur=$(( (cur + 1) % n )) ;;           # down
          '')   printf '\033[?25h\n'; return 1 ;;     # bare Esc = back
        esac
        ;;
      '')   REPLY_INDEX=$cur; printf '\033[?25h\n'; return 0 ;;   # Enter
      q|Q)  printf '\033[?25h\n'; return 1 ;;
    esac
  done
}

tui_choose_theme() {
  local names=() labels=() n i mark
  for n in $(pb_list_theme_names "$THEMES"); do names+=("$n"); done
  if [ "${#names[@]}" -eq 0 ]; then printf '\033[2J\033[HNo themes found in %s\n' "$THEMES"; pb_pause; return; fi
  for i in "${!names[@]}"; do
    pb_validate_theme "$THEMES" "${names[$i]}" 2>/dev/null && mark="✓" || mark="✗"
    labels+=("$mark ${names[$i]}")
  done
  tui_select "Choose a theme:" "${labels[@]}" || return
  printf '\033[2J\033[H'
  "$0" use "${names[$REPLY_INDEX]}" || true
  pb_pause
}

tui_set_timeout() {
  local opts=("Off - wait forever" "5 seconds" "10 seconds" "20 seconds" "30 seconds")
  local vals=(off 5 10 20 30)
  tui_select "Set boot menu timeout:" "${opts[@]}" || return
  printf '\033[2J\033[H'
  "$0" timeout "${vals[$REPLY_INDEX]}" || true
  pb_pause
}

menu_tui() {
  local active t
  while true; do
    active="$(pb_active_theme "$CONF")"
    t="$(pb_block_get "$CONF" timeout)"
    case "$t" in "") t="(not set)" ;; 0) t="off" ;; *) t="${t}s" ;; esac
    tui_select "=== prettyboot ===    theme: ${active:-none}    timeout: ${t}" \
      "Choose theme" "Set timeout" "Reset to plain rEFInd" "Quit" || break
    case "$REPLY_INDEX" in
      0) tui_choose_theme ;;
      1) tui_set_timeout ;;
      2) printf '\033[2J\033[H'; "$0" reset || true; pb_pause ;;
      3) break ;;
    esac
  done
  printf '\033[2J\033[H'
}

# Pick the arrow-key TUI when interactive; fall back to the numbered menu otherwise.
menu() {
  if [ -t 0 ] && [ -t 1 ]; then menu_tui; else menu_simple; fi
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
    [ -n "$(pb_block_get "$CONF" timeout)" ] || pb_block_set "$CONF" timeout 10
    pb_block_set "$CONF" include "themes/$name/theme.conf"
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
    pb_block_set "$CONF" timeout "$val"
    echo "Timeout: $val"
    ;;
  reset)
    pb_block_remove "$CONF"
    echo "prettyboot settings removed; plain rEFInd restored"
    ;;
  import)
    src="${2:?usage: import <dir> [name]}"
    name="${3:-$(basename "$src")}"
    pb_validate_theme_dir "$src" || exit 1
    mkdir -p "$THEMES"
    rm -rf "${THEMES:?}/$name"
    cp -r "$src" "$THEMES/$name"
    echo "Imported theme: $name"
    ;;
  set)
    key="${2:?usage: set <key> <value>}"; shift 2
    pb_block_set "$CONF" "$key" "$*"
    echo "$key = $*"
    ;;
  get)
    key="${2:?usage: get <key>}"
    pb_block_get "$CONF" "$key"
    ;;
  set-asset)
    theme="${2:?usage: set-asset <theme> <slot> <file>}"
    slot="${3:?usage: set-asset <theme> <slot> <file>}"
    file="${4:?usage: set-asset <theme> <slot> <file>}"
    pb_set_asset "$THEMES/$theme" "$slot" "$file" || exit 1
    echo "Updated $slot for $theme"
    ;;
  write-conf)
    src="${2:?usage: write-conf <file>}"
    [ -f "$src" ] || { echo "file not found: $src" >&2; exit 1; }
    [ -f "$CONF" ] && cp "$CONF" "$CONF.$(date +%Y%m%d%H%M%S).bak"
    cp "$src" "$CONF"
    echo "refind.conf updated (backup saved)"
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
