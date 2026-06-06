load helper

setup() { TMP="$(mktemp -d)"; CONF="$TMP/refind.conf"; . "$BATS_TEST_DIRNAME/../lib.sh"; }
teardown() { rm -rf "$TMP"; }

@test "block_get returns full multi-word value" {
  printf '%s\ntimeout 10\nresolution 1920 1080\n%s\n' "$PB_BEGIN" "$PB_END" > "$CONF"
  run pb_block_get "$CONF" resolution
  [ "$output" = "1920 1080" ]
}
