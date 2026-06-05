# Shared test helpers.

# make_theme <themes_dir> <name>  -- create a fully valid theme folder
make_theme() {
  mkdir -p "$1/$2/icons"
  : > "$1/$2/theme.conf"
  : > "$1/$2/background.png"
  : > "$1/$2/selection_big.png"
  : > "$1/$2/selection_small.png"
  : > "$1/$2/icons/os_linux.png"
  : > "$1/$2/icons/os_win.png"
}
