load helper

setup() {
  TMP="$(mktemp -d)"
  export REFIND_DIR="$TMP/refind"
  mkdir -p "$REFIND_DIR"
  : > "$REFIND_DIR/refind.conf"
  export SRC_THEMES="$TMP/src"
  make_theme "$SRC_THEMES" mac-dark
}
teardown() { rm -rf "$TMP"; }

@test "install deploys themes, backs up conf, writes default block" {
  run "$BATS_TEST_DIRNAME/../install.sh"
  [ "$status" -eq 0 ]
  [ -f "$REFIND_DIR/themes/mac-dark/theme.conf" ]
  [ -f "$REFIND_DIR/refind.conf.prettyboot.bak" ]
  run grep -c 'include themes/mac-dark/theme.conf' "$REFIND_DIR/refind.conf"
  [ "$output" = "1" ]
  run grep -c '^timeout 10' "$REFIND_DIR/refind.conf"
  [ "$output" = "1" ]
}

@test "install backup is not overwritten on re-run" {
  "$BATS_TEST_DIRNAME/../install.sh"
  echo "EDITED" > "$REFIND_DIR/refind.conf.prettyboot.bak"
  "$BATS_TEST_DIRNAME/../install.sh"
  run cat "$REFIND_DIR/refind.conf.prettyboot.bak"
  [ "$output" = "EDITED" ]
}
