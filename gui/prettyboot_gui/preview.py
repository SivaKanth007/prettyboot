"""Boot-menu preview rendering. `theme_assets` and the cairo painters are
GTK-free (testable headless); `build_widget` needs GTK and is imported
lazily by app.py."""
import os
import sys

from . import bootscan
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


def _sim_entries(theme_dir: str) -> list:
    """Fallback simulated dual-boot menu: (label, icon_path) per entry."""
    labels = {"os_linux.png": "Ubuntu", "os_win.png": "Windows"}
    return [(labels.get(_canon(os.path.basename(p)), "Boot entry"), p)
            for p in _entry_icons(theme_dir)]


def _real_boot_assets(theme_dir: str):
    """Scan the live ESP this theme sits on; None when not on an ESP.
    Returns (entries, tools): entries = [(label, icon_path-or-None)],
    tools = [icon_path]."""
    theme_dir = os.path.normpath(theme_dir)
    refind_dir = os.path.dirname(os.path.dirname(theme_dir))
    efi_root = os.path.dirname(refind_dir)
    if os.path.basename(efi_root).upper() != "EFI" \
            or not os.path.isdir(efi_root):
        return None
    volume = bootscan.volume_label(os.path.dirname(efi_root))
    raw = bootscan.scan_entries(efi_root, refind_dir, volume)
    if not raw:
        return None
    icon_for = {
        "win": [os.path.join(theme_dir, "icons", "os_win8.png"),
                os.path.join(theme_dir, "icons", "os_win.png"),
                os.path.join(refind_dir, "icons", "os_win.png")],
        "linux": [os.path.join(theme_dir, "icons", "os_linux.png"),
                  os.path.join(theme_dir, "icons", "os_ubuntu.png"),
                  os.path.join(refind_dir, "icons", "os_linux.png")],
        "unknown": [os.path.join(refind_dir, "icons", "os_unknown.png")],
    }
    entries = []
    for e in raw:
        icon = next((c for c in icon_for.get(e["key"], icon_for["unknown"])
                     if os.path.isfile(c)), None)
        entries.append((e["label"], icon))
    return entries, bootscan.scan_tools(efi_root, refind_dir)


def _load_surface(path):
    import cairo
    try:
        return cairo.ImageSurface.create_from_png(path)
    except (cairo.Error, OSError, MemoryError) as exc:
        print(f"prettyboot: failed to load {path}: {exc}", file=sys.stderr)
        return None


def _load_assets(theme_dir: str) -> dict:
    """Decode all surfaces once: background, selection, entries, tools.
    Entries come from the live ESP when the theme sits on one (the preview
    then replicates the user's actual boot menu); otherwise a simulated
    dual-boot menu. `tools` is None in the simulated case and may be empty
    if the ESP has no icon files; both draw outline placeholders."""
    real = _real_boot_assets(theme_dir)
    if real:
        raw_entries, tool_paths = real
        tools = [s for s in (_load_surface(p) for p in tool_paths) if s]
    else:
        raw_entries = _sim_entries(theme_dir)
        tools = None
    entries = [(label, _load_surface(p) if p else None)
               for label, p in raw_entries]
    bg = theme_assets(theme_dir)["background"]
    bg_surface = _load_surface(bg) if bg else None
    return {
        "background": bg_surface,
        "dark_bg": _is_dark(bg_surface),
        "selection_big": _load_surface(
            os.path.join(theme_dir, "selection_big.png")),
        "entries": entries,
        "tools": tools,
        "conf": L.parse_theme_conf(os.path.join(theme_dir, "theme.conf")),
    }


def _is_dark(surface) -> bool:
    """Mean luminance of a surface < 0.5? Compositing onto a small ARGB32
    scratch first normalizes whatever pixel format cairo decoded the PNG
    into (e.g. RGB96F for 16-bit PNGs) and flattens alpha over black."""
    if surface is None:
        return True
    import cairo
    sw, sh = surface.get_width(), surface.get_height()
    if sw == 0 or sh == 0:
        return True
    w, h = 32, 18
    scratch = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(scratch)
    ctx.set_source_rgb(0, 0, 0)
    ctx.paint()
    ctx.scale(w / sw, h / sh)
    ctx.set_source_surface(surface, 0, 0)
    ctx.paint()
    scratch.flush()
    data = scratch.get_data()
    stride = scratch.get_stride()
    total = 0.0
    for y in range(h):
        row = y * stride
        for x in range(w):
            b, g, r = data[row + x * 4], data[row + x * 4 + 1], data[row + x * 4 + 2]
            total += 0.2126 * r + 0.7152 * g + 0.0722 * b
    return total / (w * h * 255) < 0.5


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
    """Paint the rEFInd boot screen (real ESP scan or simulated fallback)
    onto a cairo context whose user space is width x height pixels. `assets`
    is a `_load_assets` result holding pre-decoded surfaces."""
    conf = assets["conf"]
    entries = assets["entries"]
    tools = assets["tools"]
    n_small = len(tools) if tools else 6
    out = L.layout(width, height, max(len(entries), 1), n_small,
                   conf, selected=selected)

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
    for rect, (_label, s) in zip(out["big_icons"], entries):
        if s:
            _draw_scaled(ctx, s, *rect)

    # label under the tools row (rEFInd auto-picks text color from bg
    # brightness: white-on-dark, black-on-light, with a contrasting shadow)
    if "label" not in conf["hideui"] and entries:
        idx = min(max(selected, 0), len(entries) - 1)
        text = entries[idx][0] or "Boot entry"
        ctx.select_font_face("sans")
        ctx.set_font_size(max(14, height // 50))
        ext = ctx.text_extents(text)
        cx, ty = out["label"]
        if assets.get("dark_bg", True):
            text_rgb, shadow = (1, 1, 1), (0, 0, 0, 0.6)
        else:
            text_rgb, shadow = (0, 0, 0), (1, 1, 1, 0.6)
        ctx.set_source_rgba(*shadow)
        ctx.move_to(cx - ext.width / 2 + 1, ty + ext.height + 1)
        ctx.show_text(text)
        ctx.set_source_rgb(*text_rgb)
        ctx.move_to(cx - ext.width / 2, ty + ext.height)
        ctx.show_text(text)

    # small tools row: real rEFInd icons when scanned from the ESP,
    # neutral outline placeholders in the simulated fallback
    if "tools" not in conf["hideui"]:
        if tools:
            for rect, s in zip(out["small_icons"], tools):
                _draw_scaled(ctx, s, *rect)
        else:
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
    """Return a Gtk.DrawingArea that paints the boot-screen preview at a
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
