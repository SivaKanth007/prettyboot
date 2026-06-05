load helper

PB() { REFIND_DIR="$TMP" "$BATS_TEST_DIRNAME/../prettyboot.sh" "$@"; }

setup() {
  TMP="$(mktemp -d)"
  : > "$TMP/refind.conf"
}
teardown() { rm -rf "$TMP"; }

@test "use activates a valid theme" {
  make_theme "$TMP/themes" mac-dark
  run PB use mac-dark
  [ "$status" -eq 0 ]
  run grep -c 'include themes/mac-dark/theme.conf' "$TMP/refind.conf"
  [ "$output" = "1" ]
}

@test "use refuses a broken theme and leaves conf untouched" {
  make_theme "$TMP/themes" mac-dark
  rm "$TMP/themes/mac-dark/background.png"
  run PB use mac-dark
  [ "$status" -ne 0 ]
  run grep -c 'include' "$TMP/refind.conf"
  [ "$output" = "0" ]
}

@test "list marks active theme and validity" {
  make_theme "$TMP/themes" mac-dark
  make_theme "$TMP/themes" broken
  rm "$TMP/themes/broken/theme.conf"
  PB use mac-dark
  run PB list
  [[ "$output" == *"* "*"mac-dark"* ]]
  [[ "$output" == *"broken"* ]]
}

@test "timeout sets value and preserves active include" {
  make_theme "$TMP/themes" mac-dark
  PB use mac-dark
  run PB timeout 25
  [ "$status" -eq 0 ]
  run grep -c '^timeout 25' "$TMP/refind.conf"
  [ "$output" = "1" ]
  run grep -c 'include themes/mac-dark/theme.conf' "$TMP/refind.conf"
  [ "$output" = "1" ]
}

@test "timeout off becomes 0" {
  make_theme "$TMP/themes" mac-dark
  PB use mac-dark
  PB timeout off
  run grep -c '^timeout 0' "$TMP/refind.conf"
  [ "$output" = "1" ]
}

@test "next cycles to the following valid theme" {
  make_theme "$TMP/themes" a
  make_theme "$TMP/themes" b
  PB use a
  run PB next
  [ "$status" -eq 0 ]
  run grep -c 'include themes/b/theme.conf' "$TMP/refind.conf"
  [ "$output" = "1" ]
}

@test "reset removes the managed block" {
  make_theme "$TMP/themes" mac-dark
  PB use mac-dark
  run PB reset
  [ "$status" -eq 0 ]
  run grep -c 'prettyboot' "$TMP/refind.conf"
  [ "$output" = "0" ]
}
