"""Boot-menu preview rendering. `theme_assets` and the cairo painters are
GTK-free (testable headless); `build_widget` needs GTK and is imported
lazily by app.py."""
import os
import sys

from . import layout as L


def _canon(name: str) -> str:
    """Canonical icon filename: collapse the os_win8/os_ubuntu duplicate pairs."""
    return name.replace("os_win8", "os_win").replace("os_ubuntu", "os_linux")


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


def _entry_icons(theme_dir: str) -> list:
    """Big-row entry icons: collapse the os_win/os_win8 and os_linux/os_ubuntu
    duplicate pairs, prefer linux first then windows (the dual-boot case)."""
    icons = theme_assets(theme_dir)["icons"]
    seen = {}
    for p in icons:
        key = _canon(os.path.basename(p))
        seen.setdefault(key, p)
    ordered = []
    for key in ("os_linux.png", "os_win.png"):
        if key in seen:
            ordered.append(seen.pop(key))
    ordered.extend(seen.values())
    return ordered


def _load_surface(path):
    import cairo
    try:
        return cairo.ImageSurface.create_from_png(path)
    except (cairo.Error, OSError, MemoryError) as exc:
        print(f"prettyboot: failed to load {path}: {exc}", file=sys.stderr)
        return None


def _load_assets(theme_dir: str) -> dict:
    """Decode all theme surfaces once: background, selection_big, entry icons."""
    bg = theme_assets(theme_dir)["background"]
    return {
        "background": _load_surface(bg) if bg else None,
        "selection_big": _load_surface(
            os.path.join(theme_dir, "selection_big.png")),
        "entries": [(p, _load_surface(p)) for p in _entry_icons(theme_dir)],
        "conf": L.parse_theme_conf(os.path.join(theme_dir, "theme.conf")),
    }


def _draw_scaled(ctx, surface, x, y, w, h):
    sw, sh = surface.get_width(), surface.get_height()
    if sw == 0 or sh == 0:
        return
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(w / sw, h / sh)
    ctx.set_source_surface(surface, 0, 0)
    ctx.paint()
    ctx.restore()


def _paint(ctx, width: int, height: int, assets: dict, selected: int = 0):
    """Paint the simulated rEFInd boot screen onto a cairo context whose
    user space is width x height pixels. `assets` is a `_load_assets` result
    holding pre-decoded surfaces."""
    conf = assets["conf"]
    entries = assets["entries"]
    n_small = 4  # rEFInd default tools row: shutdown/reboot/firmware/about
    out = L.layout(width, height, max(len(entries), 1), n_small,
                   conf, selected=selected)
    labels = {"os_linux.png": "Ubuntu", "os_win.png": "Windows"}

    # background (or near-black, rEFInd's default)
    ctx.set_source_rgb(0.02, 0.02, 0.02)
    ctx.paint()
    if assets["background"]:
        _draw_scaled(ctx, assets["background"], 0, 0, width, height)

    # selection highlight behind the selected big icon (real rEFInd shows
    # exactly one highlight; at boot it sits on the big row)
    if assets["selection_big"]:
        _draw_scaled(ctx, assets["selection_big"], *out["selection_big"])

    # big entry icons
    for rect, (_path, s) in zip(out["big_icons"], entries):
        if s:
            _draw_scaled(ctx, s, *rect)

    # label under the row (rEFInd auto-picks black/white from bg brightness;
    # preview approximates with white + slight shadow, fine on both themes)
    if "label" not in conf["hideui"] and entries:
        idx = min(max(selected, 0), len(entries) - 1)
        key = _canon(os.path.basename(entries[idx][0]))
        text = labels.get(key, "Boot entry")
        ctx.select_font_face("sans")
        ctx.set_font_size(max(14, height // 50))
        ext = ctx.text_extents(text)
        cx, ty = out["label"]
        ctx.set_source_rgba(0, 0, 0, 0.6)
        ctx.move_to(cx - ext.width / 2 + 1, ty + ext.height + 1)
        ctx.show_text(text)
        ctx.set_source_rgb(1, 1, 1)
        ctx.move_to(cx - ext.width / 2, ty + ext.height)
        ctx.show_text(text)

    # small tools row: neutral placeholder outlines (rEFInd built-in icons)
    if "tools" not in conf["hideui"]:
        for x, y, w, h in out["small_icons"]:
            ctx.set_source_rgba(1, 1, 1, 0.35)
            r = 6
            ctx.new_sub_path()
            ctx.arc(x + w - r, y + r, r, -1.5708, 0)
            ctx.arc(x + w - r, y + h - r, r, 0, 1.5708)
            ctx.arc(x + r, y + h - r, r, 1.5708, 3.1416)
            ctx.arc(x + r, y + r, r, 3.1416, 4.7124)
            ctx.close_path()
            ctx.set_line_width(2)
            ctx.stroke()


def render_png(theme_dir: str, out_path: str,
               width: int = 1024, height: int = 768, selected: int = 0):
    """Headless render to PNG — used for calibration against QEMU shots."""
    import cairo
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    _paint(cairo.Context(surface), width, height,
           _load_assets(theme_dir), selected)
    surface.write_to_png(out_path)


def build_widget(theme_dir: str):
    """Return a Gtk.DrawingArea that paints the simulated boot screen at a
    virtual 1920x1080 canvas, scaled to fit the widget. Imported lazily so
    non-GTK tests can import this module's pure helpers."""
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    VW, VH = 1920, 1080
    assets = _load_assets(theme_dir)

    def draw(_area, ctx, w, h):
        scale = min(w / VW, h / VH)
        ctx.translate((w - VW * scale) / 2, (h - VH * scale) / 2)
        ctx.scale(scale, scale)
        ctx.rectangle(0, 0, VW, VH)
        ctx.clip()
        _paint(ctx, VW, VH, assets)

    area = Gtk.DrawingArea()
    area.set_hexpand(True)
    area.set_vexpand(True)
    area.set_draw_func(draw)
    return area
