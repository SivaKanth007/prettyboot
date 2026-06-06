load helper

setup() { TMP="$(mktemp -d)"; CONF="$TMP/refind.conf"; . "$BATS_TEST_DIRNAME/../lib.sh"; }
teardown() { rm -rf "$TMP"; }

@test "block_get returns full multi-word value" {
  printf '%s\ntimeout 10\nresolution 1920 1080\n%s\n' "$PB_BEGIN" "$PB_END" > "$CONF"
  run pb_block_get "$CONF" resolution
  [ "$output" = "1920 1080" ]
}

@test "block_set creates block and key when absent" {
  : > "$CONF"
  pb_block_set "$CONF" timeout 10
  run pb_block_get "$CONF" timeout
  [ "$output" = "10" ]
}

@test "block_set updates existing key without touching others" {
  pb_block_set "$CONF" timeout 10
  pb_block_set "$CONF" include themes/mac-dark/theme.conf
  pb_block_set "$CONF" timeout 25
  run pb_block_get "$CONF" timeout
  [ "$output" = "25" ]
  run pb_block_get "$CONF" include
  [ "$output" = "themes/mac-dark/theme.conf" ]
}

@test "block_set writes a key only once when repeated" {
  pb_block_set "$CONF" hideui hints
  pb_block_set "$CONF" hideui hints,arrows
  run grep -c '^hideui ' "$CONF"
  [ "$output" = "1" ]
}

@test "block_unset removes a key, leaves others" {
  pb_block_set "$CONF" timeout 10
  pb_block_set "$CONF" resolution "1920 1080"
  pb_block_unset "$CONF" resolution
  run pb_block_get "$CONF" resolution
  [ -z "$output" ]
  run pb_block_get "$CONF" timeout
  [ "$output" = "10" ]
}
