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

@test "block_write then block_get returns include value" {
  conf="$TMP/refind.conf"; : > "$conf"
  pb_block_write "$conf" 10 themes/mac-dark/theme.conf
  run pb_block_get "$conf" include
  [ "$output" = "themes/mac-dark/theme.conf" ]
}

@test "block_get reads timeout value" {
  conf="$TMP/refind.conf"; : > "$conf"
  pb_block_write "$conf" 7 themes/mac-dark/theme.conf
  run pb_block_get "$conf" timeout
  [ "$output" = "7" ]
}

@test "block_write is idempotent (single block)" {
  conf="$TMP/refind.conf"; : > "$conf"
  pb_block_write "$conf" 10 themes/a/theme.conf
  pb_block_write "$conf" 5  themes/b/theme.conf
  run grep -c '>>> prettyboot >>>' "$conf"
  [ "$output" = "1" ]
  run pb_block_get "$conf" include
  [ "$output" = "themes/b/theme.conf" ]
}

@test "block_remove restores original content" {
  conf="$TMP/refind.conf"; printf 'timeout 20\nfoo bar\n' > "$conf"
  pb_block_write "$conf" 10 themes/a/theme.conf
  pb_block_remove "$conf"
  run cat "$conf"
  [ "$output" = "$(printf 'timeout 20\nfoo bar')" ]
}

@test "active_theme parses theme name from include" {
  conf="$TMP/refind.conf"; : > "$conf"
  pb_block_write "$conf" 10 themes/mac-light/theme.conf
  run pb_active_theme "$conf"
  [ "$output" = "mac-light" ]
}

@test "active_theme empty when no block" {
  conf="$TMP/refind.conf"; : > "$conf"
  run pb_active_theme "$conf"
  [ "$output" = "" ]
}

@test "block_write with empty include writes only timeout" {
  conf="$TMP/refind.conf"; : > "$conf"
  pb_block_write "$conf" 0 ""
  run pb_block_get "$conf" timeout
  [ "$output" = "0" ]
  run pb_block_get "$conf" include
  [ "$output" = "" ]
}
