load helper

PB() { REFIND_DIR="$TMP" "$BATS_TEST_DIRNAME/../prettyboot.sh" "$@"; }

setup() { TMP="$(mktemp -d)"; : > "$TMP/refind.conf"; make_theme "$TMP/themes" mac-dark; }
teardown() { rm -rf "$TMP"; }

@test "set then get round-trips a multi-word value" {
  PB set resolution "1920 1080"
  run PB get resolution
  [ "$output" = "1920 1080" ]
}

@test "get prints nothing for an unset key" {
  run PB get resolution
  [ -z "$output" ]
}

@test "curated setting survives a theme switch" {
  PB set resolution "1920 1080"
  PB use mac-dark
  run PB get resolution
  [ "$output" = "1920 1080" ]
  run grep -c 'include themes/mac-dark/theme.conf' "$TMP/refind.conf"
  [ "$output" = "1" ]
}

@test "curated setting survives a timeout change" {
  PB use mac-dark
  PB set showtools shell
  PB timeout 15
  run PB get showtools
  [ "$output" = "shell" ]
}
