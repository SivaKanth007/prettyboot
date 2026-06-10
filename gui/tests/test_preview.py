import struct
import zlib
from pathlib import Path

from prettyboot_gui import preview


def _chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def tiny_png(path, rgba):
    raw = b"\x00" + struct.pack(">4B", *rgba)
    png = (b"\x89PNG\r\n\x1a\n"
           + _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
           + _chunk(b"IDAT", zlib.compress(raw))
           + _chunk(b"IEND", b""))
    path.write_bytes(png)


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


def test_render_png(tmp_path):
    # minimal theme: 1x1 png assets are fine for rendering
    d = tmp_path / "t"
    (d / "icons").mkdir(parents=True)
    tiny_png(d / "background.png", (10, 10, 40, 255))
    tiny_png(d / "selection_big.png", (255, 255, 255, 40))
    tiny_png(d / "selection_small.png", (255, 255, 255, 40))
    tiny_png(d / "icons" / "os_linux.png", (233, 80, 14, 255))
    tiny_png(d / "icons" / "os_win.png", (0, 120, 212, 255))
    (d / "theme.conf").write_text("big_icon_size 128\nsmall_icon_size 48\n")

    out = tmp_path / "shot.png"
    from prettyboot_gui import preview
    preview.render_png(str(d), str(out), 1024, 768)
    assert out.stat().st_size > 0


def test_is_dark_classification(tmp_path):
    import cairo
    from prettyboot_gui import preview

    def solid_png(path, r, g, b):
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 64, 64)
        c = cairo.Context(s)
        c.set_source_rgb(r, g, b)
        c.paint()
        s.write_to_png(str(path))

    solid_png(tmp_path / "dark.png", 0.2, 0.2, 0.2)
    solid_png(tmp_path / "light.png", 0.9, 0.9, 0.9)
    assert preview._is_dark(
        cairo.ImageSurface.create_from_png(str(tmp_path / "dark.png"))) is True
    assert preview._is_dark(
        cairo.ImageSurface.create_from_png(str(tmp_path / "light.png"))) is False


def _theme_in_fake_esp(tmp_path):
    """Full fake ESP with the theme nested where the .deb installs it:
    <esp>/EFI/refind/themes/t — exercises the real-scan path."""
    refind = tmp_path / "EFI" / "refind"
    theme = refind / "themes" / "t"
    (theme / "icons").mkdir(parents=True)
    tiny_png(theme / "background.png", (10, 10, 40, 255))
    tiny_png(theme / "selection_big.png", (255, 255, 255, 40))
    tiny_png(theme / "icons" / "os_linux.png", (233, 80, 14, 255))
    tiny_png(theme / "icons" / "os_win8.png", (0, 120, 212, 255))
    (theme / "theme.conf").write_text("big_icon_size 128\nsmall_icon_size 48\n")
    icons = refind / "icons"
    icons.mkdir()
    for icon in ("os_unknown.png", "func_about.png", "func_hidden.png",
                 "func_shutdown.png", "func_reset.png", "func_firmware.png",
                 "tool_mok_tool.png"):
        tiny_png(icons / icon, (128, 128, 128, 255))
    (refind / "refind_x64.efi").write_bytes(b"x")
    for rel in ("Microsoft/Boot/bootmgfw.efi", "ubuntu/shimx64.efi",
                "ubuntu/mmx64.efi", "Boot/bootx64.efi", "Boot/fbx64.efi"):
        p = tmp_path / "EFI" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    return theme


def test_load_assets_uses_real_scan(tmp_path):
    from prettyboot_gui import preview
    theme = _theme_in_fake_esp(tmp_path)
    assets = preview._load_assets(str(theme))
    labels = [lbl for lbl, _s in assets["entries"]]
    assert len(labels) == 4
    assert labels[0].startswith("Boot Microsoft EFI boot")
    assert assets["tools"] is not None and len(assets["tools"]) == 6
    out = tmp_path / "shot.png"
    preview.render_png(str(theme), str(out), 1024, 768)
    assert out.stat().st_size > 0


def test_load_assets_falls_back_without_esp(tmp_path):
    from prettyboot_gui import preview
    d = tmp_path / "t"
    (d / "icons").mkdir(parents=True)
    tiny_png(d / "icons" / "os_linux.png", (233, 80, 14, 255))
    tiny_png(d / "icons" / "os_win.png", (0, 120, 212, 255))
    (d / "theme.conf").write_text("")
    assets = preview._load_assets(str(d))
    assert [lbl for lbl, _s in assets["entries"]] == ["Ubuntu", "Windows"]
    assert assets["tools"] is None
