"""Builds the live boot-menu preview. `theme_assets` is pure (testable);
`build_widget` needs GTK and is imported lazily by app.py."""
import os


def theme_assets(theme_dir: str) -> dict:
    """Resolve preview asset paths for a theme directory."""
    bg = os.path.join(theme_dir, "background.png")
    icons_dir = os.path.join(theme_dir, "icons")
    icons = []
    if os.path.isdir(icons_dir):
        for fn in sorted(os.listdir(icons_dir)):
            if fn.startswith("os_") and fn.endswith(".png"):
                icons.append(os.path.join(icons_dir, fn))
    return {
        "background": bg if os.path.isfile(bg) else None,
        "icons": icons,
    }


def build_widget(theme_dir: str):
    """Return a Gtk.Picture-based 16:9 preview overlaying OS icons on the
    background. Imported lazily so non-GTK tests can import this module's
    pure helpers."""
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, Gdk

    assets = theme_assets(theme_dir)
    overlay = Gtk.Overlay()
    overlay.set_size_request(640, 360)  # 16:9

    if assets["background"]:
        bg = Gtk.Picture.new_for_filename(assets["background"])
        bg.set_content_fit(Gtk.ContentFit.COVER)
        overlay.set_child(bg)

    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=40)
    row.set_halign(Gtk.Align.CENTER)
    row.set_valign(Gtk.Align.CENTER)
    seen = set()
    for icon in assets["icons"]:
        # collapse the os_win/os_win8 and os_linux/os_ubuntu duplicate pairs
        key = os.path.basename(icon).replace("os_win8", "os_win").replace(
            "os_ubuntu", "os_linux")
        if key in seen:
            continue
        seen.add(key)
        pic = Gtk.Picture.new_for_filename(icon)
        pic.set_size_request(96, 96)
        row.append(pic)
    overlay.add_overlay(row)
    return overlay
