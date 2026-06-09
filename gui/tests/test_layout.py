from pathlib import Path

from prettyboot_gui import layout


def test_parse_theme_conf(tmp_path):
    conf = tmp_path / "theme.conf"
    conf.write_text(
        "# comment\n"
        "banner themes/x/background.png\n"
        "selection_big themes/x/selection_big.png\n"
        "selection_small themes/x/selection_small.png\n"
        "big_icon_size 128\n"
        "small_icon_size 48\n"
        "hideui hints,arrows,badges\n"
    )
    c = layout.parse_theme_conf(str(conf))
    assert c["big_icon_size"] == 128
    assert c["small_icon_size"] == 48
    assert c["hideui"] == {"hints", "arrows", "badges"}
    assert c["selection_big"].endswith("selection_big.png")


def test_parse_theme_conf_defaults(tmp_path):
    conf = tmp_path / "theme.conf"
    conf.write_text("")
    c = layout.parse_theme_conf(str(conf))
    assert c["big_icon_size"] == 128
    assert c["small_icon_size"] == 48
    assert c["hideui"] == set()
    assert c["selection_big"] is None


def test_parse_theme_conf_missing_file(tmp_path):
    c = layout.parse_theme_conf(str(tmp_path / "absent.conf"))
    assert c["big_icon_size"] == 128
