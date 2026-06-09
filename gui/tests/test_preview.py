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


def test_render_png(tmp_path):
    # minimal theme: 1x1 png assets are fine for rendering
    import struct, zlib

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
