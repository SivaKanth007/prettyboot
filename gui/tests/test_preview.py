from pathlib import Path

from prettyboot_gui import preview


def test_theme_assets_resolves_paths(tmp_path):
    d = tmp_path / "mac-dark"
    (d / "icons").mkdir(parents=True)
    (d / "background.png").write_text("x")
    (d / "icons" / "os_win8.png").write_text("x")
    (d / "icons" / "os_ubuntu.png").write_text("x")
    a = preview.theme_assets(str(d))
    assert a["background"].endswith("background.png")
    assert any(p.endswith("os_win8.png") for p in a["icons"])
    assert any(p.endswith("os_ubuntu.png") for p in a["icons"])


def test_theme_assets_missing_background_is_none(tmp_path):
    d = tmp_path / "empty"
    (d / "icons").mkdir(parents=True)
    a = preview.theme_assets(str(d))
    assert a["background"] is None
    assert a["icons"] == []
