@test "build-assets produces valid mac-dark and mac-light themes" {
  command -v convert >/dev/null      || skip "imagemagick not installed"
  command -v rsvg-convert >/dev/null || skip "librsvg2-bin not installed"
  run "$BATS_TEST_DIRNAME/../build-assets.sh"
  [ "$status" -eq 0 ]
  for t in mac-dark mac-light; do
    for f in theme.conf background.png selection_big.png selection_small.png \
             icons/os_linux.png icons/os_win.png; do
      [ -f "$BATS_TEST_DIRNAME/../themes/$t/$f" ]
    done
    run identify -format '%m' "$BATS_TEST_DIRNAME/../themes/$t/background.png"
    [ "$output" = "PNG" ]
  done
}
