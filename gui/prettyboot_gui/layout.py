"""Pure rEFInd boot-menu geometry: theme.conf parsing and pixel layout.

No GTK imports here — everything is unit-testable. The numeric constants
are calibrated against real rEFInd screenshots captured in QEMU+OVMF
(see test/vm/capture.sh and docs/calibration/).
"""
import os

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
