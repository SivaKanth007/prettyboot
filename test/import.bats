load helper

PB() { REFIND_DIR="$TMP" "$BATS_TEST_DIRNAME/../prettyboot.sh" "$@"; }

setup() { TMP="$(mktemp -d)"; : > "$TMP/refind.conf"; }
teardown() { rm -rf "$TMP"; }

@test "import installs a valid theme dir under its folder name" {
  make_theme "$TMP/src" cool
  run PB import "$TMP/src/cool"
  [ "$status" -eq 0 ]
  [ -f "$TMP/themes/cool/theme.conf" ]
  run PB list
  [[ "$output" == *"cool"* ]]
}

@test "import honors an explicit name" {
  make_theme "$TMP/src" cool
  run PB import "$TMP/src/cool" renamed
  [ "$status" -eq 0 ]
  [ -f "$TMP/themes/renamed/theme.conf" ]
}

@test "import refuses a broken dir and installs nothing" {
  make_theme "$TMP/src" bad
  rm "$TMP/src/bad/selection_big.png"
  run PB import "$TMP/src/bad"
  [ "$status" -ne 0 ]
  [ ! -d "$TMP/themes/bad" ]
}
