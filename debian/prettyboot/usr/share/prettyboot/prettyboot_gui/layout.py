"""Pure rEFInd boot-menu geometry: theme.conf parsing and pixel layout.

No GTK imports here — everything is unit-testable. The numeric constants
are calibrated against real rEFInd screenshots captured in QEMU+OVMF
(see test/vm/capture.sh and docs/calibration/).
"""

_DEFAULTS = {
    "banner": None,
    "selection_big": None,
    "selection_small": None,
    "big_icon_size": 128,
    "small_icon_size": 48,
    "hideui": set(),
}


def parse_theme_conf(path: str) -> dict:
    """Parse the subset of theme.conf directives the preview honors.
    Unknown directives are ignored; missing file returns defaults."""
    conf = dict(_DEFAULTS)
    conf["hideui"] = set()
    try:
        with open(path) as fh:
            lines = fh.readlines()
    except OSError:
        return conf
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, val = line.partition(" ")
        val = val.strip()
        if key in ("big_icon_size", "small_icon_size"):
            try:
                conf[key] = int(val)
            except ValueError:
                pass
        elif key == "hideui":
            conf["hideui"] = {p.strip() for p in val.split(",") if p.strip()}
        elif key in ("banner", "selection_big", "selection_small"):
            conf[key] = val
    return conf


# --- geometry constants (CALIBRATED against QEMU screenshots; tweak here) ---
BIG_ROW_CENTER_Y = 0.50    # big-icon row vertical center, fraction of height
TILE_GAP = 8               # px between adjacent big tiles (rEFInd TILE_XSPACING)
LABEL_OFFSET = 16          # px from small-row tile bottom to label top
SMALL_ROW_OFFSET = 24      # px from big-row tile bottom to small-row top
SMALL_GAP = 8              # px between small tiles


def layout(width: int, height: int, n_big: int, n_small: int,
           conf: dict, selected: int = 0) -> dict:
    """Compute pixel rects (x, y, w, h) mirroring rEFInd's menu layout."""
    big = conf["big_icon_size"]
    small = conf["small_icon_size"]
    selected = min(max(selected, 0), n_big - 1)
    tile = big * 9 // 8          # selection_big tile, 9/8 of icon (rEFInd rule)
    stile = small * 4 // 3       # selection_small tile, 4/3 of icon

    # Big row: n_big tiles, centered horizontally; icons centered inside tiles.
    row_w = n_big * tile + (n_big - 1) * TILE_GAP
    row_x = (width - row_w) // 2
    tile_y = int(height * BIG_ROW_CENTER_Y) - tile // 2
    big_icons = []
    for i in range(n_big):
        tx = row_x + i * (tile + TILE_GAP)
        pad = (tile - big) // 2
        big_icons.append((tx + pad, tile_y + pad, big, big))
    sel_x = row_x + selected * (tile + TILE_GAP)
    selection_big = (sel_x, tile_y, tile, tile)

    # Small (tools) row: centered, below the big row.
    srow_w = n_small * stile + (n_small - 1) * SMALL_GAP
    srow_x = (width - srow_w) // 2
    stile_y = tile_y + tile + SMALL_ROW_OFFSET
    small_icons = []
    for i in range(n_small):
        tx = srow_x + i * (stile + SMALL_GAP)
        pad = (stile - small) // 2
        small_icons.append((tx + pad, stile_y + pad, small, small))
    selection_small = (srow_x, stile_y, stile, stile)

    # Label: centered on screen, below the small (tools) row.
    label = (width // 2, stile_y + stile + LABEL_OFFSET)

    return {
        "background": (0, 0, width, height),
        "big_icons": big_icons,
        "selection_big": selection_big,
        "small_icons": small_icons,
        "selection_small": selection_small,
        "label": label,
    }
