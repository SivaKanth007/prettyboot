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


def _conf():
    return dict(layout._DEFAULTS, hideui=set())


def test_layout_big_row_centered_horizontally():
    out = layout.layout(1024, 768, n_big=2, n_small=4, conf=_conf(), selected=0)
    big = out["big_icons"]
    assert len(big) == 2
    left_gap = big[0][0]
    right_gap = 1024 - (big[-1][0] + big[-1][2])
    assert abs(left_gap - right_gap) <= 1


def test_layout_selection_big_centered_on_selected():
    out = layout.layout(1024, 768, n_big=2, n_small=4, conf=_conf(), selected=1)
    sx, sy, sw, sh = out["selection_big"]
    ix, iy, iw, ih = out["big_icons"][1]
    assert abs((sx + sw / 2) - (ix + iw / 2)) <= 1
    assert abs((sy + sh / 2) - (iy + ih / 2)) <= 1
    assert sw > iw  # selection tile is 9/8 of the icon


def test_layout_small_row_below_big_row():
    out = layout.layout(1024, 768, n_big=2, n_small=4, conf=_conf(), selected=0)
    big_bottom = max(y + h for _, y, _, h in out["big_icons"])
    small_top = min(y for _, y, _, _ in out["small_icons"])
    assert small_top > big_bottom
    assert len(out["small_icons"]) == 4


def test_layout_label_below_big_row_centered():
    out = layout.layout(1024, 768, n_big=2, n_small=4, conf=_conf(), selected=0)
    cx, ty = out["label"]
    assert abs(cx - 512) <= 1
    big_bottom = max(y + h for _, y, _, h in out["big_icons"])
    assert ty > big_bottom


def test_layout_selected_out_of_range_clamped():
    out = layout.layout(1024, 768, n_big=2, n_small=4, conf=_conf(), selected=9)
    assert out["selection_big"] == layout.layout(
        1024, 768, n_big=2, n_small=4, conf=_conf(), selected=1)["selection_big"]


def test_layout_everything_inside_screen():
    out = layout.layout(800, 600, n_big=3, n_small=5, conf=_conf(), selected=2)
    rects = (out["big_icons"] + out["small_icons"]
             + [out["selection_big"], out["selection_small"]])
    for x, y, w, h in rects:
        assert 0 <= x and 0 <= y and x + w <= 800 and y + h <= 600
