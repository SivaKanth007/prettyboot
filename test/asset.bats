load helper

PB() { REFIND_DIR="$TMP" "$BATS_TEST_DIRNAME/../prettyboot.sh" "$@"; }

setup() {
  TMP="$(mktemp -d)"; : > "$TMP/refind.conf"
  make_theme "$TMP/themes" mac-dark
  printf 'NEWBG' > "$TMP/new.png"
  printf 'NEWWIN' > "$TMP/win.png"
}
teardown() { rm -rf "$TMP"; }

@test "set-asset background replaces background.png" {
  run PB set-asset mac-dark background "$TMP/new.png"
  [ "$status" -eq 0 ]
  run cat "$TMP/themes/mac-dark/background.png"
  [ "$output" = "NEWBG" ]
}

@test "set-asset win syncs os_win.png and os_win8.png" {
  run PB set-asset mac-dark win "$TMP/win.png"
  [ "$status" -eq 0 ]
  run cat "$TMP/themes/mac-dark/icons/os_win.png"
  [ "$output" = "NEWWIN" ]
  run cat "$TMP/themes/mac-dark/icons/os_win8.png"
  [ "$output" = "NEWWIN" ]
}

@test "set-asset rejects an unknown slot" {
  run PB set-asset mac-dark bogus "$TMP/new.png"
  [ "$status" -ne 0 ]
}
