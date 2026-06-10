# Real Boot-Scan Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The GUI preview shows the user's *actual* boot menu — real entries scanned from the ESP, real rEFInd tool icons — instead of a simulated two-entry menu, with a clean fallback when no ESP is readable.

**Architecture:** New pure module `gui/prettyboot_gui/bootscan.py` reproduces rEFInd's loader scan (classify → win/linux/unknown, rEFInd-style labels, tool detection). `preview.py::_load_assets` derives the ESP location from the theme path, consumes the scan, and resolves icons (theme icons for win/linux, the ESP's own `os_unknown.png` / `func_*.png` for the rest). Any failure → today's simulated preview. `app.py` untouched.

**Tech Stack:** Python 3 (stdlib only in bootscan; cairo in preview), pytest via `.venv`.

**Spec:** `docs/superpowers/specs/2026-06-09-real-bootscan-preview-design.md`

**Repo:** `/home/deva/GitHub/prettyboot`, currently on `main` — Task 1 creates the work branch.

**How to run tests (MUST run from `gui/`):**
`cd /home/deva/GitHub/prettyboot/gui && ../.venv/bin/python -m pytest tests -q` (baseline: 21 passed, 1 skipped)

**Ground truth (user's machine, verified):** ESP label `SYSTEM`; loaders
`EFI/Microsoft/Boot/bootmgfw.efi`, `EFI/ubuntu/{shimx64,grubx64,mmx64}.efi`,
`EFI/Boot/{bootx64,fbx64,mmx64}.efi`, `EFI/refind/refind_x64.efi`. Real menu
photos (`/home/deva/Downloads/Boot_Menu/`) show exactly 4 big entries
(win, ubuntu, unknown, ubuntu) and 6 tools (mok-key, about, hidden, shutdown,
reboot, firmware); label "Boot Microsoft EFI boot from SYSTEM".

## File Structure

| Path | Status | Responsibility |
|------|--------|----------------|
| `gui/prettyboot_gui/bootscan.py` | create | pure ESP scan: entries, tools, volume label |
| `gui/prettyboot_gui/preview.py` | modify | consume scan in `_load_assets`; real tool icons; fallback |
| `gui/tests/test_bootscan.py` | create | fake-ESP scan tests |
| `gui/tests/test_preview.py` | modify | real-ESP render test + shared tiny-png helper |

---

### Task 1: Create the work branch

- [ ] **Step 1:**

```bash
cd /home/deva/GitHub/prettyboot
git checkout -b feat/real-bootscan-preview
```

Expected: `Switched to a new branch 'feat/real-bootscan-preview'`. Verify clean tree with `git status --short`.

---

### Task 2: `bootscan.scan_entries` (pure, TDD)

**Files:**
- Create: `gui/prettyboot_gui/bootscan.py`
- Create: `gui/tests/test_bootscan.py`

- [ ] **Step 1: Write the failing tests** — create `gui/tests/test_bootscan.py`:

```python
from pathlib import Path

from prettyboot_gui import bootscan


def _touch(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")


def _fake_esp(tmp_path: Path) -> Path:
    """Replica of the user's real ESP layout (ground truth in the plan)."""
    efi = tmp_path / "EFI"
    _touch(efi / "Microsoft" / "Boot" / "bootmgfw.efi")
    _touch(efi / "Microsoft" / "Boot" / "bootmgr.efi")
    _touch(efi / "Microsoft" / "Boot" / "memtest.efi")
    _touch(efi / "ubuntu" / "shimx64.efi")
    _touch(efi / "ubuntu" / "grubx64.efi")
    _touch(efi / "ubuntu" / "mmx64.efi")
    _touch(efi / "Boot" / "bootx64.efi")
    _touch(efi / "Boot" / "fbx64.efi")
    _touch(efi / "Boot" / "mmx64.efi")
    _touch(efi / "refind" / "refind_x64.efi")
    for icon in ("os_unknown.png", "func_about.png", "func_hidden.png",
                 "func_shutdown.png", "func_reset.png", "func_firmware.png",
                 "tool_mok_tool.png"):
        _touch(efi / "refind" / "icons" / icon)
    return efi


def test_scan_entries_matches_real_menu(tmp_path):
    efi = _fake_esp(tmp_path)
    entries = bootscan.scan_entries(str(efi), str(efi / "refind"), "SYSTEM")
    keys = [e["key"] for e in entries]
    # user's real menu: windows, ubuntu, then the fallback pair
    assert keys == ["win", "linux", "linux", "unknown"]
    assert entries[0]["label"] == "Boot Microsoft EFI boot from SYSTEM"
    assert entries[1]["label"] == "Boot ubuntu from SYSTEM"


def test_scan_entries_excludes_refind_and_tools(tmp_path):
    efi = _fake_esp(tmp_path)
    entries = bootscan.scan_entries(str(efi), str(efi / "refind"), "SYSTEM")
    labels = " ".join(e["label"] for e in entries)
    assert "refind" not in labels.lower()
    assert "mm" not in labels.lower()          # MokManager not an entry
    assert "bootmgr " not in labels.lower()    # only bootmgfw for Microsoft
    assert "memtest" not in labels.lower()
    assert "grub" not in labels.lower()        # shim supersedes grub


def test_scan_entries_no_volume_label(tmp_path):
    efi = _fake_esp(tmp_path)
    entries = bootscan.scan_entries(str(efi), str(efi / "refind"), "")
    assert entries[0]["label"] == "Boot Microsoft EFI boot"


def test_scan_entries_missing_root(tmp_path):
    assert bootscan.scan_entries(str(tmp_path / "nope"), str(tmp_path), "X") == []
```

- [ ] **Step 2: Run to verify failure**

Run: `cd /home/deva/GitHub/prettyboot/gui && ../.venv/bin/python -m pytest tests/test_bootscan.py -q`
Expected: FAIL — `ModuleNotFoundError: ... bootscan`.

- [ ] **Step 3: Create `gui/prettyboot_gui/bootscan.py`:**

```python
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
```

- [ ] **Step 4: Run the tests**

Run: `cd /home/deva/GitHub/prettyboot/gui && ../.venv/bin/python -m pytest tests/test_bootscan.py -q`
Expected: 4 pass. (If ordering of the `Boot` dir pair differs from the test, fix the implementation, not the test — the test encodes the photo ground truth with `bootx64` (linux) before `fbx64` (unknown) per sorted filename order; final order is confirmed at the Task 5 acceptance gate.)

NOTE: the test expects keys `["win", "linux", "linux", "unknown"]` — Microsoft, ubuntu/shim, Boot/bootx64 (fallback→linux), Boot/fbx64 (unknown). For that, `Boot` must be scanned AFTER `ubuntu` (so `saw_linux` is True) — guaranteed by `_dir_sort_key`.

- [ ] **Step 5: Commit**

```bash
cd /home/deva/GitHub/prettyboot
git add gui/prettyboot_gui/bootscan.py gui/tests/test_bootscan.py
git commit -m "feat(gui): ESP boot-entry scanner mirroring rEFInd (pure, tested)"
```

---

### Task 3: `bootscan.scan_tools` + `volume_label` (TDD)

**Files:**
- Modify: `gui/prettyboot_gui/bootscan.py`
- Modify: `gui/tests/test_bootscan.py`

- [ ] **Step 1: Append failing tests** to `gui/tests/test_bootscan.py`:

```python
def test_scan_tools_real_layout(tmp_path):
    efi = _fake_esp(tmp_path)
    tools = bootscan.scan_tools(str(efi), str(efi / "refind"))
    names = [Path(t).name for t in tools]
    # mok present (mm*.efi on ESP), no shell; then the always-on five
    assert names == ["tool_mok_tool.png", "func_about.png", "func_hidden.png",
                     "func_shutdown.png", "func_reset.png", "func_firmware.png"]
    assert all(Path(t).is_file() for t in tools)


def test_scan_tools_skips_missing_icons(tmp_path):
    efi = _fake_esp(tmp_path)
    (efi / "refind" / "icons" / "func_hidden.png").unlink()
    names = [Path(t).name for t in
             bootscan.scan_tools(str(efi), str(efi / "refind"))]
    assert "func_hidden.png" not in names


def test_volume_label_failure_is_empty(tmp_path):
    assert bootscan.volume_label(str(tmp_path / "not-a-mountpoint")) == ""
```

- [ ] **Step 2: Run to verify failure**

Run: `cd /home/deva/GitHub/prettyboot/gui && ../.venv/bin/python -m pytest tests/test_bootscan.py -q`
Expected: new tests FAIL — `scan_tools` undefined.

- [ ] **Step 3: Append to `gui/prettyboot_gui/bootscan.py`:**

```python
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
```

- [ ] **Step 4: Run the tests**

Run: `cd /home/deva/GitHub/prettyboot/gui && ../.venv/bin/python -m pytest tests/test_bootscan.py -q`
Expected: 7 pass.

- [ ] **Step 5: Commit**

```bash
cd /home/deva/GitHub/prettyboot
git add gui/prettyboot_gui/bootscan.py gui/tests/test_bootscan.py
git commit -m "feat(gui): tool-row detection and volume label for boot scan"
```

---

### Task 4: Wire the scan into the preview (with fallback)

**Files:**
- Modify: `gui/prettyboot_gui/preview.py`
- Modify: `gui/tests/test_preview.py`

The entries contract changes from `(icon_path, surface)` to `(label, surface)`;
tools become real surfaces when scanned, `None` for the outline fallback.

- [ ] **Step 1: Refactor the tiny-PNG helper to module level** in
`gui/tests/test_preview.py` — move the `_chunk`/`tiny_png` inner functions of
`test_render_png` to module level (keep `test_render_png` behavior identical):

```python
import struct
import zlib


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
```

and have `test_render_png` use them (delete its inner copies and the inner
`import struct, zlib`).

- [ ] **Step 2: Write the failing real-ESP render test** — append to
`gui/tests/test_preview.py`:

```python
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
```

- [ ] **Step 3: Run to verify failure**

Run: `cd /home/deva/GitHub/prettyboot/gui && ../.venv/bin/python -m pytest tests/test_preview.py -q`
Expected: the two new tests FAIL (`assets["entries"]` holds icon paths, no
`tools` key); `test_render_png` and `test_is_dark_classification` still pass.

- [ ] **Step 4: Modify `gui/prettyboot_gui/preview.py`:**

4a. Import bootscan — change line 7 area:

```python
from . import bootscan
from . import layout as L
```

4b. Add after `_entry_icons` (keep `_entry_icons` itself unchanged):

```python
def _sim_entries(theme_dir: str) -> list:
    """Fallback simulated dual-boot menu: (label, icon_path) per entry."""
    labels = {"os_linux.png": "Ubuntu", "os_win.png": "Windows"}
    return [(labels.get(_canon(os.path.basename(p)), "Boot entry"), p)
            for p in _entry_icons(theme_dir)]


def _real_boot_assets(theme_dir: str):
    """Scan the live ESP this theme sits on; None when not on an ESP.
    Returns (entries, tools): entries = [(label, icon_path-or-None)],
    tools = [icon_path]."""
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
                os.path.join(theme_dir, "icons", "os_win.png")],
        "linux": [os.path.join(theme_dir, "icons", "os_linux.png")],
        "unknown": [os.path.join(refind_dir, "icons", "os_unknown.png")],
    }
    entries = []
    for e in raw:
        icon = next((c for c in icon_for[e["key"]] if os.path.isfile(c)), None)
        entries.append((e["label"], icon))
    return entries, bootscan.scan_tools(efi_root, refind_dir)
```

4c. Replace `_load_assets` with:

```python
def _load_assets(theme_dir: str) -> dict:
    """Decode all surfaces once: background, selection, entries, tools.
    Entries come from the live ESP when the theme sits on one (the preview
    then replicates the user's actual boot menu); otherwise a simulated
    dual-boot menu. `tools` is None in the simulated case (drawn as
    outline placeholders)."""
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
```

4d. In `_paint`, replace the `n_small = 6` line and the `labels = ...` line:

```python
    tools = assets["tools"]
    n_small = len(tools) if tools else 6
```

(delete the `labels = {...}` dict line entirely), replace the label-text block's
key lookup — the two lines

```python
        key = _canon(os.path.basename(entries[idx][0]))
        text = labels.get(key, "Boot entry")
```

become

```python
        text = entries[idx][0] or "Boot entry"
```

and the big-icon loop unpack comment changes meaning only (`(_path, s)` →
`(_label, s)`):

```python
    for rect, (_label, s) in zip(out["big_icons"], entries):
```

4e. Replace the tools-row block at the end of `_paint`:

```python
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
```

- [ ] **Step 5: Run the full suite**

Run: `cd /home/deva/GitHub/prettyboot/gui && ../.venv/bin/python -m pytest tests -q`
Expected: 30 passed, 1 skipped (21 baseline + 7 bootscan + 2 preview).

- [ ] **Step 6: Commit**

```bash
cd /home/deva/GitHub/prettyboot
git add gui/prettyboot_gui/preview.py gui/prettyboot_gui/bootscan.py gui/tests/
git commit -m "feat(gui): preview replicates the real boot menu via ESP scan"
```

---

### Task 5: Photo acceptance gate (USER)

No new code unless the comparison demands tuning.

- [ ] **Step 1: Render the active theme against the real ESP** (the machine's
theme dir lives at `/boot/efi/EFI/refind/themes/mac-dark`, world-readable):

```bash
cd /home/deva/GitHub/prettyboot/gui
../.venv/bin/python -c "
from prettyboot_gui import preview
preview.render_png('/boot/efi/EFI/refind/themes/mac-dark',
                   '/tmp/real-preview.png', 1280, 720)
print('ok')"
```

- [ ] **Step 2: LOOK at `/tmp/real-preview.png`** (Read tool). Expected: 4 big
entries — windows glass icon FIRST with the glass selection tile and label
"Boot Microsoft EFI boot from SYSTEM", ubuntu second, then the fallback pair
(ubuntu + 3-circles unknown in either order); 6 real tool icons (key, info,
recycle, power, reboot, chip). Compare against
`/home/deva/Downloads/Boot_Menu/WhatsApp Image 2026-06-09 at 9.09.59 PM.jpeg`.

- [ ] **Step 3: Side-by-side for the user:**

```bash
convert "/home/deva/Downloads/Boot_Menu/WhatsApp Image 2026-06-09 at 9.09.59 PM.jpeg" \
  -resize 1280x /tmp/photo.png
montage /tmp/photo.png /tmp/real-preview.png -tile 1x2 -geometry +0+4 \
  /tmp/photo-vs-preview.png
```

Send `/tmp/photo-vs-preview.png` to the user (SendUserFile). **Wait for
verdict.** Permitted tuning if the user wants the order/classification
adjusted to match the photo exactly: `_dir_sort_key`, `_classify`, and the
fallback-pair handling in `bootscan.py` (update `test_scan_entries_matches_real_menu`
to the corrected ground truth in the same commit).

- [ ] **Step 4: Commit any tuning**

```bash
cd /home/deva/GitHub/prettyboot
git add gui/prettyboot_gui/bootscan.py gui/tests/test_bootscan.py
git commit -m "fix(gui): tune boot-scan order/classification to match real menu"
```

---

### Task 6: Full verification & finish

- [ ] **Step 1:**

```bash
cd /home/deva/GitHub/prettyboot && bats test/ | tail -1
cd gui && ../.venv/bin/python -m pytest tests -q
```
Expected: bats all ok; pytest 30 passed, 1 skipped.

- [ ] **Step 2:** Clean tree check (`git status --short`), review
`git log --oneline main..HEAD`.

- [ ] **Step 3:** Use superpowers:finishing-a-development-branch (merge to
main + push + rebuild `.deb` + reinstall on the user's machine so the
installed GUI gets the real-scan preview).
