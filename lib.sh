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
