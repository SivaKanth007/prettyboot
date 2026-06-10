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
    saw_linux = False  # spans directories: _dir_sort_key scans Boot last so
    # the fallback copy is classified after the real distro loader is seen
    for d in dirs:
        droot = os.path.join(efi_root, d)
        if not os.path.isdir(droot) or os.path.realpath(droot) == refind_real:
            continue
        loaders = []
        for _sub, dirs, files in os.walk(droot):
            dirs.sort()
            for fn in sorted(files):
                if fn.lower().endswith(".efi") and not _skip_file(fn):
                    loaders.append(fn)
        if any(fn.lower() == "bootmgfw.efi" for fn in loaders):
            # the Microsoft tree boots only through bootmgfw.efi; the other
            # .efi files there (cbmr_driver, SecureBootRecovery, ...) are
            # support binaries rEFInd never lists
            loaders = [fn for fn in loaders if fn.lower() == "bootmgfw.efi"]
        names = {fn.lower() for fn in loaders}
        for fn in loaders:
            if fn.lower().startswith("grub") and any(
                    n.startswith("shim") for n in names):
                continue  # shim supersedes grub in the same top-level directory tree
            key, desc = _classify(d, fn, saw_linux)
            if key == "linux":
                saw_linux = True
            entries.append({"label": f"Boot {desc}{suffix}", "key": key})
    return entries


def scan_tools(efi_root: str, refind_dir: str) -> list:
    """Ordered absolute icon paths for the tools row rEFInd will show.
    Conditional tools first (mok, shell), then rEFInd's defaults; an icon
    is included only if its PNG exists in <refind_dir>/icons/."""
    have_mok = have_shell = False
    for _sub, _dirs, files in os.walk(efi_root):
        for fn in files:
            low = fn.lower()
            if low.endswith(".efi"):
                if low.startswith(("mm", "mokmanager")):
                    have_mok = True
                elif low.startswith("shell"):
                    have_shell = True
    candidates = []
    if have_mok:
        candidates.append("tool_mok_tool.png")
    if have_shell:
        candidates.append("tool_shell.png")
    candidates += ["func_about.png", "func_hidden.png", "func_shutdown.png",
                   "func_reset.png", "func_firmware.png"]
    icons = os.path.join(refind_dir, "icons")
    return [p for p in (os.path.join(icons, c) for c in candidates)
            if os.path.isfile(p)]


def volume_label(mountpoint: str) -> str:
    """Filesystem label of the partition mounted at mountpoint; '' on
    any failure (missing tools, not a mountpoint, no label)."""
    try:
        dev = subprocess.run(
            ["findmnt", "-no", "SOURCE", mountpoint],
            capture_output=True, text=True, check=True).stdout.strip()
        if not dev:
            return ""
        return subprocess.run(
            ["lsblk", "-no", "LABEL", dev],
            capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""
