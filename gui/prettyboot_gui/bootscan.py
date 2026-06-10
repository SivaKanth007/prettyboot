"""Scan the ESP for the boot entries and tools rEFInd shows at boot.

Pure file-system logic so it is unit-testable; the single impure helper
(`volume_label`) shells out and is isolated so tests inject the label.
Entries carry a semantic icon key ("win" | "linux" | "unknown") — the
preview resolves keys to actual icon files.
"""
import os
import subprocess

# binaries that surface in the tools row (or not at all), never as entries
_SKIP_PREFIXES = ("mm", "mokmanager", "memtest", "bootmgr.")


def _skip_file(fn: str) -> bool:
    return fn.lower().startswith(_SKIP_PREFIXES)


def _dir_sort_key(name: str):
    """rEFInd order observed on real hardware: Microsoft first, named
    distro dirs next, the fallback Boot dir last."""
    low = name.lower()
    if low == "microsoft":
        return (0, low)
    if low == "boot":
        return (2, low)
    return (1, low)


def _classify(dirname: str, filename: str, saw_linux: bool):
    """Return (icon key, rEFInd-style description) for one loader."""
    low = (dirname + "/" + filename).lower()
    if "microsoft" in low or "bootmgfw" in low:
        return "win", "Microsoft EFI boot"
    if "ubuntu" in low or "shim" in low or "grub" in low:
        return "linux", dirname
    if filename.lower().startswith("boot") and saw_linux:
        # EFI/Boot/bootx64.efi is the fallback copy of the installed
        # distro's loader; rEFInd shows it with the distro icon
        return "linux", "Fallback boot loader"
    return "unknown", os.path.splitext(filename)[0]


def scan_entries(efi_root: str, refind_dir: str, volume: str) -> list:
    """[{"label": str, "key": "win"|"linux"|"unknown"}] in menu order."""
    refind_real = os.path.realpath(refind_dir)
    try:
        dirs = sorted(os.listdir(efi_root), key=_dir_sort_key)
    except OSError:
        return []
    suffix = f" from {volume}" if volume else ""
    entries = []
    saw_linux = False
    for d in dirs:
        droot = os.path.join(efi_root, d)
        if not os.path.isdir(droot) or os.path.realpath(droot) == refind_real:
            continue
        loaders = []
        for sub, _dirs, files in os.walk(droot):
            for fn in sorted(files):
                if fn.lower().endswith(".efi") and not _skip_file(fn):
                    loaders.append(fn)
        names = {fn.lower() for fn in loaders}
        for fn in loaders:
            if fn.lower().startswith("grub") and any(
                    n.startswith("shim") for n in names):
                continue  # shim supersedes grub in the same directory
            key, desc = _classify(d, fn, saw_linux)
            if key == "linux":
                saw_linux = True
            entries.append({"label": f"Boot {desc}{suffix}", "key": key})
    return entries
