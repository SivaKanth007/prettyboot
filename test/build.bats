setup() { TMP="$(mktemp -d)"; }
teardown() { rm -rf "$TMP"; }

# Runs build-assets.sh in a COPY so it never clobbers the committed theme assets.
@test "build-assets produces valid mac-dark and mac-light themes" {
  command -v convert >/dev/null      || skip "imagemagick not installed"
  command -v rsvg-convert >/dev/null || skip "librsvg2-bin not installed"
  cp "$BATS_TEST_DIRNAME/../build-assets.sh" "$TMP/build-assets.sh"
  cp -r "$BATS_TEST_DIRNAME/../assets" "$TMP/assets"
  run bash -c "cd '$TMP' && ./build-assets.sh"
  [ "$status" -eq 0 ]
  for t in mac-dark mac-light; do
    for f in theme.conf background.png selection_big.png selection_small.png \
             icons/os_linux.png icons/os_ubuntu.png icons/os_win.png icons/os_win8.png; do
      [ -f "$TMP/themes/$t/$f" ]
    done
    run identify -format '%m' "$TMP/themes/$t/background.png"
    [ "$output" = "PNG" ]
  done
}
