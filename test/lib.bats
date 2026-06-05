load helper

setup() { TMP="$(mktemp -d)"; . "$BATS_TEST_DIRNAME/../lib.sh"; }
teardown() { rm -rf "$TMP"; }

@test "valid theme passes validation" {
  make_theme "$TMP/themes" mac-dark
  run pb_validate_theme "$TMP/themes" mac-dark
  [ "$status" -eq 0 ]
}

@test "missing required file fails validation" {
  make_theme "$TMP/themes" mac-dark
  rm "$TMP/themes/mac-dark/background.png"
  run pb_validate_theme "$TMP/themes" mac-dark
  [ "$status" -eq 1 ]
  [[ "$output" == *background.png* ]]
}

@test "unknown theme fails validation" {
  run pb_validate_theme "$TMP/themes" nope
  [ "$status" -eq 1 ]
}

@test "list_theme_names returns sorted names" {
  make_theme "$TMP/themes" zeta
  make_theme "$TMP/themes" alpha
  run pb_list_theme_names "$TMP/themes"
  [ "${lines[0]}" = "alpha" ]
  [ "${lines[1]}" = "zeta" ]
}
