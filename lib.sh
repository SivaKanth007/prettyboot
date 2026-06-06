# lib.sh - shared helpers for prettyboot. Source this file; defines pb_* functions.

PB_BEGIN='# >>> prettyboot >>>'
PB_END='# <<< prettyboot <<<'

# Entries (relative to a theme dir) required for a theme to be valid.
PB_REQUIRED='theme.conf background.png selection_big.png selection_small.png icons'

# pb_validate_theme <themes_dir> <name>
# Prints what is missing to stderr. Returns 0 if valid, 1 otherwise.
pb_validate_theme() {
  local dir="$1/$2" missing="" item
  if [ ! -d "$dir" ]; then
    echo "theme '$2' not found" >&2
    return 1
  fi
  for item in $PB_REQUIRED; do
    [ -e "$dir/$item" ] || missing="$missing $item"
  done
  if [ -n "$missing" ]; then
    echo "theme '$2' missing:$missing" >&2
    return 1
  fi
  return 0
}

# pb_list_theme_names <themes_dir>  -> prints theme folder names, one per line, sorted
pb_list_theme_names() {
  [ -d "$1" ] || return 0
  local d
  for d in "$1"/*/; do
    [ -d "$d" ] || continue
    basename "$d"
  done | sort
}

# pb_block_remove <conf>  -- delete the managed block in place (no-op if absent)
pb_block_remove() {
  local conf="$1"
  [ -f "$conf" ] || return 0
  awk -v b="$PB_BEGIN" -v e="$PB_END" '
    $0==b {skip=1; next}
    $0==e {skip=0; next}
    !skip {print}
  ' "$conf" > "$conf.tmp" && mv "$conf.tmp" "$conf"
}

# pb_block_get <conf> <key>  -- print value of key inside the block (multi-word safe)
pb_block_get() {
  local conf="$1" key="$2"
  [ -f "$conf" ] || return 0
  awk -v b="$PB_BEGIN" -v e="$PB_END" -v k="$key" '
    $0==b {inb=1; next}
    $0==e {inb=0; next}
    inb && $1==k { $1=""; sub(/^[ \t]+/,""); print; exit }
  ' "$conf"
}

# pb_block_set <conf> <key> <value...>  -- upsert "key value" inside the block.
# Creates the conf and/or the block if missing. Replaces an existing key in place.
pb_block_set() {
  local conf="$1" key="$2"; shift 2; local value="$*"
  [ -f "$conf" ] || : > "$conf"
  if ! grep -qF "$PB_BEGIN" "$conf"; then
    { echo "$PB_BEGIN"; echo "$PB_END"; } >> "$conf"
  fi
  awk -v b="$PB_BEGIN" -v e="$PB_END" -v k="$key" -v val="$value" '
    $0==b {inb=1; print; next}
    inb && $0==e { if (!done) print k" "val; inb=0; print; next }
    inb && $1==k { if (!done) { print k" "val; done=1 } ; next }
    {print}
  ' "$conf" > "$conf.tmp" && mv "$conf.tmp" "$conf"
}

# pb_block_unset <conf> <key>  -- remove a key line from inside the block (no-op if absent)
pb_block_unset() {
  local conf="$1" key="$2"
  [ -f "$conf" ] || return 0
  awk -v b="$PB_BEGIN" -v e="$PB_END" -v k="$key" '
    $0==b {inb=1; print; next}
    $0==e {inb=0; print; next}
    inb && $1==k { next }
    {print}
  ' "$conf" > "$conf.tmp" && mv "$conf.tmp" "$conf"
}

# pb_block_write <conf> <timeout> <include>  -- replace the block with these values
# include may be empty (writes timeout only). File is created if missing.
pb_block_write() {
  local conf="$1" timeout="$2" include="$3"
  [ -f "$conf" ] || : > "$conf"
  pb_block_remove "$conf"
  {
    echo "$PB_BEGIN"
    echo "timeout $timeout"
    [ -n "$include" ] && echo "include $include"
    echo "$PB_END"
  } >> "$conf"
}

# pb_active_theme <conf>  -- print active theme name parsed from the include line
pb_active_theme() {
  local inc
  inc="$(pb_block_get "$1" include)"
  case "$inc" in
    themes/*/theme.conf) inc="${inc#themes/}"; echo "${inc%/theme.conf}" ;;
  esac
}

# pb_deploy_themes <src_themes_dir> <dest_themes_dir>  -- copy all themes
pb_deploy_themes() {
  mkdir -p "$2"
  cp -r "$1"/. "$2"/
}
