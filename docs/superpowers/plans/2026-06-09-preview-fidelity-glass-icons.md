# Preview Fidelity, Glass Icons & Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 9 audit bugs, replace flat theme icons with a glassmorphism set, and make the GUI preview reproduce rEFInd's real boot-screen layout, calibrated against QEMU+OVMF screenshots.

**Architecture:** The GUI stays a thin wrapper over the bash CLI. New pure module `gui/prettyboot_gui/layout.py` holds rEFInd geometry math (testable, no GTK); `preview.py` gains a cairo renderer using it; a dev-only `test/vm/capture.sh` boots real rEFInd in QEMU to produce ground-truth screenshots for calibrating layout constants. Glass icons are SVG sources in `assets/`, rendered by the existing `build-assets.sh`.

**Tech Stack:** bash, Python 3 + GTK4 (PyGObject) + cairo, pytest (run via `.venv`), bats, rsvg-convert + ImageMagick, QEMU + OVMF + mtools (dev only).

**Spec:** `docs/superpowers/specs/2026-06-09-preview-fidelity-glass-icons-design.md`

**Repo:** `/home/deva/GitHub/prettyboot`, branch `feat/gui-app`.

**How to run tests:**
- bats: `cd /home/deva/GitHub/prettyboot && bats test/`
- pytest: `cd /home/deva/GitHub/prettyboot/gui && ../.venv/bin/python -m pytest tests -q` (MUST run from `gui/`)

## File Structure

| Path | Status | Responsibility |
|------|--------|----------------|
| `gui/prettyboot_gui/engine.py` | modify | CLI wrapper fixes (zip import, stderr, temp file) |
| `gui/prettyboot_gui/app.py` | modify | threading, banner, drop feedback, fullscreen |
| `gui/prettyboot_gui/layout.py` | create | pure rEFInd geometry math + theme.conf parser |
| `gui/prettyboot_gui/preview.py` | modify | cairo renderer replacing icon-row overlay |
| `gui/tests/test_engine.py` | modify | new engine tests |
| `gui/tests/test_layout.py` | create | layout math + parser tests |
| `assets/os_win.svg`, `assets/os_ubuntu.svg`, `assets/prettyboot.svg` | create | glass SVG sources |
| `assets/prettyboot.png` | create (rendered) | app icon |
| `build-assets.sh` | modify | render icons from `assets/` SVGs |
| `debian/install` | modify | install app icon |
| `test/vm/capture.sh` | create | dev-only QEMU screenshot harness |
| `docs/calibration/` | create | ground-truth screenshots + side-by-sides |

---

### Task 1: Commit pending REFIND_DIR fix (bug 9)

`gui/prettyboot_gui/app.py` already contains the uncommitted change honoring `REFIND_DIR` from env (line 11). Just commit it.

- [ ] **Step 1: Verify the working tree change is only this**

Run: `cd /home/deva/GitHub/prettyboot && git diff`
Expected: only `app.py` hunk adding `import os` and `REFIND_DIR = os.environ.get("REFIND_DIR", "/boot/efi/EFI/refind")`.

- [ ] **Step 2: Commit**

```bash
git add gui/prettyboot_gui/app.py
git commit -m "fix(gui): honor REFIND_DIR env so GUI can run against a sandbox"
```

---

### Task 2: Fix zip import with explicit name (bug 2)

**Files:**
- Modify: `gui/prettyboot_gui/engine.py:100`
- Test: `gui/tests/test_engine.py`

Current bug: `src = dirs[0] if len(dirs) == 1 and not name else tmp` — when `name` is passed and the zip has a single top-level folder, it imports the extraction root (which *contains* the theme folder) instead of the theme folder itself, producing an invalid theme.

- [ ] **Step 1: Write the failing test** (append to `gui/tests/test_engine.py`)

```python
def test_import_zip_with_name(refind, tmp_path):
    theme = _make_theme(tmp_path / "pack", "original")
    zpath = tmp_path / "original.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        for p in theme.rglob("*"):
            z.write(p, p.relative_to(tmp_path / "pack"))
    engine.import_path(str(zpath), name="renamed")
    themes = {n: valid for n, _, valid in engine.list_themes()}
    assert themes.get("renamed") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/deva/GitHub/prettyboot/gui && ../.venv/bin/python -m pytest tests/test_engine.py::test_import_zip_with_name -q`
Expected: FAIL (theme "renamed" missing or invalid).

- [ ] **Step 3: Fix** — in `engine.py` `import_path`, change

```python
        src = dirs[0] if len(dirs) == 1 and not name else tmp
```
to
```python
        src = dirs[0] if len(dirs) == 1 else tmp
```

- [ ] **Step 4: Run the full engine test file**

Run: `cd /home/deva/GitHub/prettyboot/gui && ../.venv/bin/python -m pytest tests/test_engine.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add gui/prettyboot_gui/engine.py gui/tests/test_engine.py
git commit -m "fix(gui): zip import with explicit name uses inner theme folder"
```

---

### Task 3: Surface stderr from failed write ops (bug 3)

**Files:**
- Modify: `gui/prettyboot_gui/engine.py:25-28` (`_write`)
- Test: `gui/tests/test_engine.py`

- [ ] **Step 1: Write the failing test** (append to `gui/tests/test_engine.py`)

```python
def test_write_failure_surfaces_stderr(refind):
    with pytest.raises(RuntimeError, match="not found"):
        engine.set_asset("nope", "background", "/nonexistent/file.png")
```

(The CLI's `set-asset` prints `source file not found: ...` to stderr and exits non-zero.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/deva/GitHub/prettyboot/gui && ../.venv/bin/python -m pytest tests/test_engine.py::test_write_failure_surfaces_stderr -q`
Expected: FAIL — `subprocess.CalledProcessError` raised, not `RuntimeError` with the stderr text.

- [ ] **Step 3: Replace `_write`** in `engine.py`:

```python
def _write(*args: str) -> None:
    pkexec = os.environ.get("PRETTYBOOT_PKEXEC", "pkexec")
    cmd = ([pkexec] if pkexec else []) + [_bin(), *args]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        msg = out.stderr.strip() or f"exit status {out.returncode}"
        raise RuntimeError(msg)
```

- [ ] **Step 4: Run the full engine test file**

Run: `cd /home/deva/GitHub/prettyboot/gui && ../.venv/bin/python -m pytest tests/test_engine.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add gui/prettyboot_gui/engine.py gui/tests/test_engine.py
git commit -m "fix(gui): error dialogs show CLI stderr, not just exit code"
```

---

### Task 4: write_conf temp file — 0600 perms + cleanup (bug 6)

**Files:**
- Modify: `gui/prettyboot_gui/engine.py:76-80` (`write_conf`)
- Test: `gui/tests/test_engine.py`

- [ ] **Step 1: Write the failing test** (append to `gui/tests/test_engine.py`; add `import tempfile` to the file's imports)

```python
def test_write_conf_cleans_temp_file(refind, monkeypatch):
    created = []
    real = tempfile.mkstemp

    def spy(*a, **k):
        fd, path = real(*a, **k)
        created.append(path)
        return fd, path

    monkeypatch.setattr(engine.tempfile, "mkstemp", spy)
    engine.write_conf("timeout 5\n")
    assert (refind / "refind.conf").read_text() == "timeout 5\n"
    assert created and not os.path.exists(created[0])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/deva/GitHub/prettyboot/gui && ../.venv/bin/python -m pytest tests/test_engine.py::test_write_conf_cleans_temp_file -q`
Expected: FAIL — `mkstemp` never called (current code uses `NamedTemporaryFile(delete=False)`), so `created` is empty.

- [ ] **Step 3: Replace `write_conf`** in `engine.py` (`mkstemp` creates the file 0600 by default):

```python
def write_conf(text: str) -> None:
    fd, tmp = tempfile.mkstemp(suffix=".conf")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        _write("write-conf", tmp)
    finally:
        os.unlink(tmp)
```

- [ ] **Step 4: Run the full engine test file**

Run: `cd /home/deva/GitHub/prettyboot/gui && ../.venv/bin/python -m pytest tests/test_engine.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add gui/prettyboot_gui/engine.py gui/tests/test_engine.py
git commit -m "fix(gui): write-conf temp file is 0600 and deleted after use"
```

---

### Task 5: Run write ops off the GTK main thread (bug 4)

**Files:**
- Modify: `gui/prettyboot_gui/app.py` (`_run` at :161-170, plus its callers)

The current `_run` blocks the main loop while pkexec shows its password dialog. Move work to a thread; deliver results back via `GLib.idle_add`. Add an optional `on_done` callback so callers needing post-write actions (preview refresh, banner hide) sequence correctly — today `_on_bg_drop` refreshes the preview *before* the write finishes.

No automated test (GTK main-loop behavior); verify by compile + full suite + the sandbox visual check in Task 13.

- [ ] **Step 1: Add `import threading`** to the top of `app.py` (after `import os`).

- [ ] **Step 2: Replace `_run`** with:

```python
    def _run(self, work, on_done=None):
        """Run a write op on a worker thread; report failure in a dialog and
        refresh the theme list back on the main thread."""
        def worker():
            try:
                work()
                err = None
            except Exception as exc:
                err = str(exc)
            GLib.idle_add(self._after_run, err, on_done)
        threading.Thread(target=worker, daemon=True).start()

    def _after_run(self, err, on_done):
        if err:
            dlg = Gtk.AlertDialog()
            dlg.set_message("Operation failed")
            dlg.set_detail(err)
            dlg.show(self)
        elif on_done:
            on_done()
        self._reload_themes()
        return False
```

- [ ] **Step 3: Fix the `_on_bg_drop` ordering** — replace its body's run+refresh lines:

```python
        if row and path:
            self._run(lambda: engine.set_asset(row.theme_name, "background", path),
                      on_done=lambda: self._on_theme_selected(None, row))
        return True
```

(`row.theme_name` stays readable even after `_reload_themes` rebuilds the list.)

- [ ] **Step 4: Compile check + full suites**

Run:
```bash
cd /home/deva/GitHub/prettyboot && python3 -m py_compile gui/prettyboot_gui/app.py
cd gui && ../.venv/bin/python -m pytest tests -q && cd .. && bats test/ | tail -1
```
Expected: compile clean, pytest all pass, bats `ok 43` (or final count line, all ok).

- [ ] **Step 5: Commit**

```bash
git add gui/prettyboot_gui/app.py
git commit -m "fix(gui): write ops run off the main thread; no freeze during pkexec"
```

---

### Task 6: Hide setup banner after success (bug 5)

**Files:**
- Modify: `gui/prettyboot_gui/app.py:45-48`

- [ ] **Step 1: Replace the banner block** in `_themes_tab`:

```python
        if not engine.has_managed_block():
            self.setup_banner = Gtk.Button(label="Set up boot menu")
            self.setup_banner.connect(
                "clicked",
                lambda _b: self._run(
                    engine.setup_boot,
                    on_done=lambda: self.setup_banner.set_visible(False)))
            rail.prepend(self.setup_banner)
```

- [ ] **Step 2: Compile check**

Run: `python3 -m py_compile gui/prettyboot_gui/app.py`
Expected: silent.

- [ ] **Step 3: Commit**

```bash
git add gui/prettyboot_gui/app.py
git commit -m "fix(gui): hide first-run setup banner after setup succeeds"
```

---

### Task 7: Feedback when background dropped with no theme selected (bug 7)

**Files:**
- Modify: `gui/prettyboot_gui/app.py` (`_on_bg_drop`)

- [ ] **Step 1: Replace `_on_bg_drop`** with:

```python
    def _on_bg_drop(self, _t, value, _x, _y):
        row = self.theme_list.get_selected_row()
        path = value.get_path()
        if not row:
            dlg = Gtk.AlertDialog()
            dlg.set_message("Select a theme first")
            dlg.set_detail("Pick the theme that should get this background, "
                           "then drop the image again.")
            dlg.show(self)
            return True
        if path:
            self._run(lambda: engine.set_asset(row.theme_name, "background", path),
                      on_done=lambda: self._on_theme_selected(None, row))
        return True
```

- [ ] **Step 2: Compile check**

Run: `python3 -m py_compile gui/prettyboot_gui/app.py`
Expected: silent.

- [ ] **Step 3: Commit**

```bash
git add gui/prettyboot_gui/app.py
git commit -m "fix(gui): tell user to select a theme before dropping a background"
```

---

### Task 8: Fullscreen ⛶ preview button (bug 8)

**Files:**
- Modify: `gui/prettyboot_gui/app.py` (`_themes_tab` preview area)

- [ ] **Step 1: In `_themes_tab`, replace the preview-holder block** (the three `self.preview_holder` lines plus `box.append(self.preview_holder)`) with:

```python
        self.preview_holder = Gtk.Box()
        self.preview_holder.set_hexpand(True)
        self.preview_holder.set_vexpand(True)
        wrap = Gtk.Overlay()
        wrap.set_child(self.preview_holder)
        fs_btn = Gtk.Button(label="⛶")
        fs_btn.set_tooltip_text("Fullscreen preview (Esc to close)")
        fs_btn.set_halign(Gtk.Align.END)
        fs_btn.set_valign(Gtk.Align.START)
        fs_btn.set_margin_top(6)
        fs_btn.set_margin_end(6)
        fs_btn.connect("clicked", self._on_fullscreen)
        wrap.add_overlay(fs_btn)
        box.append(wrap)
```

Keep the existing `bg_drop` controller lines attached to `self.preview_holder` as they are.

- [ ] **Step 2: Add the handler** (method on `Window`):

```python
    def _on_fullscreen(self, _btn):
        row = self.theme_list.get_selected_row()
        if not row:
            return
        win = Gtk.Window(transient_for=self)
        win.set_child(preview.build_widget(
            f"{REFIND_DIR}/themes/{row.theme_name}"))
        key = Gtk.EventControllerKey()
        key.connect(
            "key-pressed",
            lambda _c, val, _code, _state:
                (win.close() or True) if val == Gdk.KEY_Escape else False)
        win.add_controller(key)
        win.fullscreen()
        win.present()
```

- [ ] **Step 3: Compile check + pytest**

Run:
```bash
python3 -m py_compile gui/prettyboot_gui/app.py
cd gui && ../.venv/bin/python -m pytest tests -q
```
Expected: clean / all pass.

- [ ] **Step 4: Commit**

```bash
git add gui/prettyboot_gui/app.py
git commit -m "feat(gui): fullscreen preview button (spec gap)"
```

---

### Task 9: Glass icon SVGs + app icon + packaging (bug 1 + Part 2)

**Files:**
- Create: `assets/os_win.svg`, `assets/os_ubuntu.svg`, `assets/prettyboot.svg`
- Modify: `build-assets.sh` (icons section, lines 30-58)
- Modify: `debian/install`
- Generated: theme icon PNGs (both themes) + `assets/prettyboot.png`

- [ ] **Step 1: Create `assets/os_win.svg`** — Windows four-pane with glass treatment (gradient panes, diagonal sheen, edge highlight, soft shadow):

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <defs>
    <linearGradient id="pane" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#5db2ff" stop-opacity="0.96"/>
      <stop offset="1" stop-color="#0a5fd0" stop-opacity="0.90"/>
    </linearGradient>
    <linearGradient id="sheen" x1="0" y1="0" x2="0.6" y2="1">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.50"/>
      <stop offset="0.45" stop-color="#ffffff" stop-opacity="0.10"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>
    <clipPath id="panes">
      <rect x="26" y="26" width="97" height="97" rx="16"/>
      <rect x="133" y="26" width="97" height="97" rx="16"/>
      <rect x="26" y="133" width="97" height="97" rx="16"/>
      <rect x="133" y="133" width="97" height="97" rx="16"/>
    </clipPath>
    <filter id="soft" x="-25%" y="-25%" width="150%" height="150%">
      <feDropShadow dx="0" dy="5" stdDeviation="8"
                    flood-color="#000000" flood-opacity="0.35"/>
    </filter>
  </defs>
  <g filter="url(#soft)">
    <rect x="26" y="26" width="97" height="97" rx="16" fill="url(#pane)"/>
    <rect x="133" y="26" width="97" height="97" rx="16" fill="url(#pane)"/>
    <rect x="26" y="133" width="97" height="97" rx="16" fill="url(#pane)"/>
    <rect x="133" y="133" width="97" height="97" rx="16" fill="url(#pane)"/>
  </g>
  <path d="M0 0 H256 L0 256 Z" fill="url(#sheen)" clip-path="url(#panes)"/>
  <g fill="none" stroke="#ffffff" stroke-opacity="0.35" stroke-width="2"
     clip-path="url(#panes)">
    <rect x="27" y="27" width="95" height="95" rx="15"/>
    <rect x="134" y="27" width="95" height="95" rx="15"/>
    <rect x="27" y="134" width="95" height="95" rx="15"/>
    <rect x="134" y="134" width="95" height="95" rx="15"/>
  </g>
</svg>
```

- [ ] **Step 2: Create `assets/os_ubuntu.svg`** — glass orange squircle, white circle-of-friends (geometry reused from the old inline SVG in `build-assets.sh:37-48`):

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">
  <defs>
    <linearGradient id="base" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ff8a3c"/>
      <stop offset="1" stop-color="#cf3a00"/>
    </linearGradient>
    <linearGradient id="sheen" x1="0" y1="0" x2="0.4" y2="1">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.45"/>
      <stop offset="0.5" stop-color="#ffffff" stop-opacity="0.08"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>
    <clipPath id="sq"><rect width="1024" height="1024" rx="230"/></clipPath>
    <filter id="soft" x="-15%" y="-15%" width="130%" height="130%">
      <feDropShadow dx="0" dy="18" stdDeviation="30"
                    flood-color="#000000" flood-opacity="0.35"/>
    </filter>
  </defs>
  <rect width="1024" height="1024" rx="230" fill="url(#base)" filter="url(#soft)"/>
  <path d="M0 0 H1024 L0 1024 Z" fill="url(#sheen)" clip-path="url(#sq)"/>
  <rect x="6" y="6" width="1012" height="1012" rx="224" fill="none"
        stroke="#ffffff" stroke-opacity="0.30" stroke-width="8"
        clip-path="url(#sq)"/>
  <g fill="#fff" transform="translate(93.2,-352.8) scale(0.803)">
    <circle cx="226.58835" cy="1056.07411" r="109.02696"/>
    <circle cx="680.64509" cy="817.00695" r="109.02696"/>
    <circle cx="656.08182" cy="1337.26719" r="109.02696"/>
    <path d="M472.48179,1336.66575a265.525,265.525,0,0,1-181.07121-138.09821,156.94811,156.94811,0,0,1-93.21911,11.45831,354.9352,354.9352,0,0,0,255.53721,214.16456,359.21054,359.21054,0,0,0,77.41948,7.967,156.00315,156.00315,0,0,1-31.92236-91.15471C490.24607,1340.00523,481.27719,1338.548,472.48179,1336.66575Z"/>
    <path d="M807.7978,1297.22089A356.70056,356.70056,0,0,0,825.67268,878.702a157.14405,157.14405,0,0,1-61.30976,71.80309,267.293,267.293,0,0,1-8.73685,265.48842A156.34662,156.34662,0,0,1,807.7978,1297.22089Z"/>
    <path d="M218.17628,899.71905q4.1505-.2277,8.30533-.22553A157.3464,157.3464,0,0,1,309.164,923.039,265.90648,265.90648,0,0,1,523.2722,808.52964a158.08773,158.08773,0,0,1,33.076-88.42024C419.24532,709.25176,286.02405,780.001,218.17628,899.71905Z"/>
  </g>
</svg>
```

- [ ] **Step 3: Create `assets/prettyboot.svg`** — app icon: indigo glass squircle (matches mac-dark palette) + white power glyph:

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">
  <defs>
    <linearGradient id="base" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#7a64e8"/>
      <stop offset="1" stop-color="#241b4f"/>
    </linearGradient>
    <linearGradient id="sheen" x1="0" y1="0" x2="0.4" y2="1">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.40"/>
      <stop offset="0.5" stop-color="#ffffff" stop-opacity="0.07"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>
    <clipPath id="sq"><rect width="1024" height="1024" rx="230"/></clipPath>
    <filter id="soft" x="-15%" y="-15%" width="130%" height="130%">
      <feDropShadow dx="0" dy="18" stdDeviation="30"
                    flood-color="#000000" flood-opacity="0.35"/>
    </filter>
  </defs>
  <rect width="1024" height="1024" rx="230" fill="url(#base)" filter="url(#soft)"/>
  <path d="M0 0 H1024 L0 1024 Z" fill="url(#sheen)" clip-path="url(#sq)"/>
  <rect x="6" y="6" width="1012" height="1012" rx="224" fill="none"
        stroke="#ffffff" stroke-opacity="0.28" stroke-width="8"
        clip-path="url(#sq)"/>
  <g stroke="#ffffff" stroke-width="64" fill="none" stroke-linecap="round">
    <path d="M512 280 v 240"/>
    <path d="M383 407 A 200 200 0 1 0 641 407"/>
  </g>
</svg>
```

- [ ] **Step 4: Render each SVG to a scratch PNG and LOOK at it** (the power-glyph arc flags and sheen clips must be verified visually, not assumed):

```bash
cd /home/deva/GitHub/prettyboot
for s in os_win os_ubuntu prettyboot; do
  rsvg-convert -w 256 -h 256 "assets/$s.svg" -o "/tmp/check-$s.png"
done
```

Read `/tmp/check-os_win.png`, `/tmp/check-os_ubuntu.png`, `/tmp/check-prettyboot.png` with the Read tool. Expected: glassy gradient panes/squircles with a visible diagonal sheen; power glyph = vertical bar over an open ring with the gap at the top. If the arc looks wrong (gap at bottom, or full circle), adjust the arc's `large-arc`/`sweep` flags (try `0 0` then `1 1`) and re-render until correct.

- [ ] **Step 5: Modify `build-assets.sh`** — replace the whole inline-SVG icons section (lines 30-58, from `# --- icons:` through `rm -rf "$tmp"`) with:

```bash
# --- icons: glass set rendered from assets/*.svg (Microsoft-Authenticator-style
# glassmorphism: gradient base, diagonal sheen, edge highlight, soft shadow) ---
for d in "$md" "$ml"; do
  rsvg-convert -w 256 -h 256 "$here/assets/os_ubuntu.svg" -o "$d/icons/os_ubuntu.png"
  cp "$d/icons/os_ubuntu.png" "$d/icons/os_linux.png"   # linux fallback = ubuntu badge
  rsvg-convert -w 256 -h 256 "$here/assets/os_win.svg"    -o "$d/icons/os_win.png"
  # rEFInd tags the modern Windows Boot Manager as "win8" and looks for os_win8
  # FIRST; without it, it falls back to its built-in tilted Win8 logo. Provide it.
  cp "$d/icons/os_win.png" "$d/icons/os_win8.png"
done
# --- desktop app icon (referenced by gui/prettyboot.desktop Icon=prettyboot) ---
rsvg-convert -w 256 -h 256 "$here/assets/prettyboot.svg" -o "$here/assets/prettyboot.png"
```

- [ ] **Step 6: Run the asset build**

Run: `cd /home/deva/GitHub/prettyboot && ./build-assets.sh`
Expected: `Generated themes: mac-dark, mac-light`; `git status` shows the 8 theme icon PNGs changed and `assets/prettyboot.png` new.

- [ ] **Step 7: Add the icon to packaging** — append to `debian/install`:

```
assets/prettyboot.png        usr/share/icons/hicolor/256x256/apps/
```

- [ ] **Step 8: Run bats (theme validity must hold)**

Run: `bats test/ | tail -1`
Expected: all ok.

- [ ] **Step 9: Commit**

```bash
git add assets/ build-assets.sh debian/install themes/
git commit -m "feat: glassmorphism icon set (win/ubuntu) + shipped app icon"
```

---

### Task 10: theme.conf parser (Part 3, pure)

**Files:**
- Create: `gui/prettyboot_gui/layout.py`
- Create: `gui/tests/test_layout.py`

- [ ] **Step 1: Write failing tests** — create `gui/tests/test_layout.py`:

```python
from pathlib import Path

from prettyboot_gui import layout


def test_parse_theme_conf(tmp_path):
    conf = tmp_path / "theme.conf"
    conf.write_text(
        "# comment\n"
        "banner themes/x/background.png\n"
        "selection_big themes/x/selection_big.png\n"
        "selection_small themes/x/selection_small.png\n"
        "big_icon_size 128\n"
        "small_icon_size 48\n"
        "hideui hints,arrows,badges\n"
    )
    c = layout.parse_theme_conf(str(conf))
    assert c["big_icon_size"] == 128
    assert c["small_icon_size"] == 48
    assert c["hideui"] == {"hints", "arrows", "badges"}
    assert c["selection_big"].endswith("selection_big.png")


def test_parse_theme_conf_defaults(tmp_path):
    conf = tmp_path / "theme.conf"
    conf.write_text("")
    c = layout.parse_theme_conf(str(conf))
    assert c["big_icon_size"] == 128
    assert c["small_icon_size"] == 48
    assert c["hideui"] == set()
    assert c["selection_big"] is None


def test_parse_theme_conf_missing_file(tmp_path):
    c = layout.parse_theme_conf(str(tmp_path / "absent.conf"))
    assert c["big_icon_size"] == 128
```

- [ ] **Step 2: Run to verify failure**

Run: `cd /home/deva/GitHub/prettyboot/gui && ../.venv/bin/python -m pytest tests/test_layout.py -q`
Expected: FAIL — `ModuleNotFoundError: prettyboot_gui.layout`.

- [ ] **Step 3: Create `gui/prettyboot_gui/layout.py`** (parser half; `layout()` comes in Task 11):

```python
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
```

- [ ] **Step 4: Run tests**

Run: `cd /home/deva/GitHub/prettyboot/gui && ../.venv/bin/python -m pytest tests/test_layout.py -q`
Expected: 3 pass.

- [ ] **Step 5: Commit**

```bash
git add gui/prettyboot_gui/layout.py gui/tests/test_layout.py
git commit -m "feat(gui): theme.conf parser for preview (pure, tested)"
```

---

### Task 11: layout() geometry math (Part 3, pure)

**Files:**
- Modify: `gui/prettyboot_gui/layout.py`
- Modify: `gui/tests/test_layout.py`

Tests assert *invariants* (centering, ordering, containment), not absolute pixels — so later calibration tweaks constants without breaking tests.

- [ ] **Step 1: Append failing tests** to `gui/tests/test_layout.py`:

```python
def _conf():
    return dict(layout._DEFAULTS, hideui=set())


def test_layout_big_row_centered_horizontally():
    out = layout.layout(1024, 768, n_big=2, n_small=4, conf=_conf(), selected=0)
    big = out["big_icons"]
    assert len(big) == 2
    left_gap = big[0][0]
    right_gap = 1024 - (big[-1][0] + big[-1][2])
    assert abs(left_gap - right_gap) <= 1


def test_layout_selection_big_centered_on_selected():
    out = layout.layout(1024, 768, n_big=2, n_small=4, conf=_conf(), selected=1)
    sx, sy, sw, sh = out["selection_big"]
    ix, iy, iw, ih = out["big_icons"][1]
    assert abs((sx + sw / 2) - (ix + iw / 2)) <= 1
    assert abs((sy + sh / 2) - (iy + ih / 2)) <= 1
    assert sw > iw  # selection tile is 9/8 of the icon


def test_layout_small_row_below_big_row():
    out = layout.layout(1024, 768, n_big=2, n_small=4, conf=_conf(), selected=0)
    big_bottom = max(y + h for _, y, _, h in out["big_icons"])
    small_top = min(y for _, y, _, _ in out["small_icons"])
    assert small_top > big_bottom
    assert len(out["small_icons"]) == 4


def test_layout_label_below_big_row_centered():
    out = layout.layout(1024, 768, n_big=2, n_small=4, conf=_conf(), selected=0)
    cx, ty = out["label"]
    assert abs(cx - 512) <= 1
    big_bottom = max(y + h for _, y, _, h in out["big_icons"])
    assert ty > big_bottom


def test_layout_everything_inside_screen():
    out = layout.layout(800, 600, n_big=3, n_small=5, conf=_conf(), selected=2)
    rects = (out["big_icons"] + out["small_icons"]
             + [out["selection_big"], out["selection_small"]])
    for x, y, w, h in rects:
        assert 0 <= x and 0 <= y and x + w <= 800 and y + h <= 600
```

- [ ] **Step 2: Run to verify failure**

Run: `cd /home/deva/GitHub/prettyboot/gui && ../.venv/bin/python -m pytest tests/test_layout.py -q`
Expected: new tests FAIL — `layout.layout` undefined.

- [ ] **Step 3: Append to `gui/prettyboot_gui/layout.py`**:

```python
# --- geometry constants (CALIBRATED against QEMU screenshots; tweak here) ---
BIG_ROW_CENTER_Y = 0.50    # big-icon row vertical center, fraction of height
TILE_GAP = 8               # px between adjacent big tiles (rEFInd TILE_XSPACING)
LABEL_OFFSET = 24          # px from big-row tile bottom to label top
SMALL_ROW_OFFSET = 72      # px from big-row tile bottom to small-row top
SMALL_GAP = 8              # px between small tiles


def layout(width: int, height: int, n_big: int, n_small: int,
           conf: dict, selected: int = 0) -> dict:
    """Compute pixel rects (x, y, w, h) mirroring rEFInd's menu layout."""
    big = conf["big_icon_size"]
    small = conf["small_icon_size"]
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

    # Label: centered on screen, below the big tiles.
    label = (width // 2, tile_y + tile + LABEL_OFFSET)

    # Small row: centered, below the label area.
    srow_w = n_small * stile + (n_small - 1) * SMALL_GAP
    srow_x = (width - srow_w) // 2
    stile_y = tile_y + tile + SMALL_ROW_OFFSET
    small_icons = []
    for i in range(n_small):
        tx = srow_x + i * (stile + SMALL_GAP)
        pad = (stile - small) // 2
        small_icons.append((tx + pad, stile_y + pad, small, small))
    selection_small = (srow_x, stile_y, stile, stile)

    return {
        "background": (0, 0, width, height),
        "big_icons": big_icons,
        "selection_big": selection_big,
        "small_icons": small_icons,
        "selection_small": selection_small,
        "label": label,
    }
```

- [ ] **Step 4: Run tests**

Run: `cd /home/deva/GitHub/prettyboot/gui && ../.venv/bin/python -m pytest tests/test_layout.py -q`
Expected: 8 pass.

- [ ] **Step 5: Commit**

```bash
git add gui/prettyboot_gui/layout.py gui/tests/test_layout.py
git commit -m "feat(gui): rEFInd menu geometry math (pure, tested)"
```

---

### Task 12: Cairo preview renderer (Part 3, GTK)

**Files:**
- Modify: `gui/prettyboot_gui/preview.py` (replace `build_widget`; add `_paint` and `render_png`)
- Test: `gui/tests/test_preview.py` (existing pure tests must keep passing) + new render test

`_paint` draws onto any cairo context at a virtual canvas size — shared by the live widget and headless PNG rendering (used for calibration in Task 14).

- [ ] **Step 1: Write a failing headless-render test** — append to `gui/tests/test_preview.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `cd /home/deva/GitHub/prettyboot/gui && ../.venv/bin/python -m pytest tests/test_preview.py -q`
Expected: new test FAILs — `render_png` undefined. (Existing `theme_assets` tests still pass.)

- [ ] **Step 3: Rewrite `gui/prettyboot_gui/preview.py`** — keep `theme_assets` exactly as is; replace `build_widget` and add the renderer:

```python
"""Boot-menu preview rendering. `theme_assets` and the cairo painters are
GTK-free (testable headless); `build_widget` needs GTK and is imported
lazily by app.py."""
import os

from . import layout as L


def theme_assets(theme_dir: str) -> dict:
    # ... UNCHANGED from current file ...


def _entry_icons(theme_dir: str) -> list:
    """Big-row entry icons: collapse the os_win/os_win8 and os_linux/os_ubuntu
    duplicate pairs, prefer linux first then windows (the dual-boot case)."""
    icons = theme_assets(theme_dir)["icons"]
    seen = {}
    for p in icons:
        key = os.path.basename(p).replace("os_win8", "os_win").replace(
            "os_ubuntu", "os_linux")
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
    except Exception:
        return None


def _draw_scaled(ctx, surface, x, y, w, h):
    import cairo  # noqa: F401
    sw, sh = surface.get_width(), surface.get_height()
    if sw == 0 or sh == 0:
        return
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(w / sw, h / sh)
    ctx.set_source_surface(surface, 0, 0)
    ctx.paint()
    ctx.restore()


def _paint(ctx, width: int, height: int, theme_dir: str, selected: int = 0):
    """Paint the simulated rEFInd boot screen onto a cairo context whose
    user space is width x height pixels."""
    conf = L.parse_theme_conf(os.path.join(theme_dir, "theme.conf"))
    entries = _entry_icons(theme_dir)
    n_small = 4  # rEFInd default tools row: shutdown/reboot/firmware/about
    out = L.layout(width, height, max(len(entries), 1), n_small,
                   conf, selected=selected)
    labels = {"os_linux.png": "Ubuntu", "os_win.png": "Windows"}

    # background (or near-black, rEFInd's default)
    ctx.set_source_rgb(0.02, 0.02, 0.02)
    ctx.paint()
    bg = theme_assets(theme_dir)["background"]
    if bg:
        s = _load_surface(bg)
        if s:
            _draw_scaled(ctx, s, 0, 0, width, height)

    # selection highlight behind the selected big icon
    sel = _load_surface(os.path.join(theme_dir, "selection_big.png"))
    if sel:
        _draw_scaled(ctx, sel, *out["selection_big"])

    # big entry icons
    for rect, icon in zip(out["big_icons"], entries):
        s = _load_surface(icon)
        if s:
            _draw_scaled(ctx, s, *rect)

    # label under the row (rEFInd auto-picks black/white from bg brightness;
    # preview approximates with white + slight shadow, fine on both themes)
    if "label" not in conf["hideui"] and entries:
        key = os.path.basename(entries[min(selected, len(entries) - 1)]).replace(
            "os_win8", "os_win").replace("os_ubuntu", "os_linux")
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

    # small tools row: neutral placeholder glyphs (rEFInd built-in icons)
    if "tools" not in conf["hideui"]:
        ssel = _load_surface(os.path.join(theme_dir, "selection_small.png"))
        if ssel:
            _draw_scaled(ctx, ssel, *out["selection_small"])
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
    _paint(cairo.Context(surface), width, height, theme_dir, selected)
    surface.write_to_png(out_path)


def build_widget(theme_dir: str):
    """Return a Gtk.DrawingArea that paints the simulated boot screen at a
    virtual 1920x1080 canvas, scaled to fit the widget. Imported lazily so
    non-GTK tests can import this module's pure helpers."""
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    VW, VH = 1920, 1080

    def draw(_area, ctx, w, h):
        scale = min(w / VW, h / VH)
        ctx.translate((w - VW * scale) / 2, (h - VH * scale) / 2)
        ctx.scale(scale, scale)
        ctx.rectangle(0, 0, VW, VH)
        ctx.clip()
        _paint(ctx, VW, VH, theme_dir)

    area = Gtk.DrawingArea()
    area.set_hexpand(True)
    area.set_vexpand(True)
    area.set_draw_func(draw)
    return area
```

(The `# ... UNCHANGED ...` marker means: keep the existing `theme_assets` body verbatim from the current file — do not retype it incorrectly.)

- [ ] **Step 4: Run full pytest**

Run: `cd /home/deva/GitHub/prettyboot/gui && ../.venv/bin/python -m pytest tests -q`
Expected: all pass (launch test may skip).

- [ ] **Step 5: Visual smoke check** — render both bundled themes and LOOK at them:

```bash
cd /home/deva/GitHub/prettyboot/gui
../.venv/bin/python -c "
from prettyboot_gui import preview
for t in ('mac-dark', 'mac-light'):
    preview.render_png(f'../themes/{t}', f'/tmp/preview-{t}.png', 1024, 768)
print('ok')
"
```
Read `/tmp/preview-mac-dark.png` and `/tmp/preview-mac-light.png` with the Read tool. Expected: background gradient, two glass icons side by side with a rounded highlight behind the first, "Ubuntu" label below, 4 small outline squares at the bottom.

- [ ] **Step 6: Commit**

```bash
git add gui/prettyboot_gui/preview.py gui/tests/test_preview.py
git commit -m "feat(gui): cairo preview reproducing rEFInd menu layout"
```

---

### Task 13: Sandbox visual check of the GUI (bugs 4-8 + new preview)

No code. Launch the GUI against a throwaway sandbox so the user can see the
threading fix, banner, fullscreen button, and new preview live.

- [ ] **Step 1: Build sandbox + launch** (background):

```bash
cd /home/deva/GitHub/prettyboot
sb="$(mktemp -d /tmp/prettyboot-demo.XXXX)"
cp -r themes "$sb/themes"
: > "$sb/refind.conf"
echo "$sb" > /tmp/prettyboot-demo-path
DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 REFIND_DIR="$sb" \
  PRETTYBOOT_BIN="$PWD/prettyboot.sh" PRETTYBOOT_PKEXEC= \
  PYTHONPATH="$PWD/gui" python3 -m prettyboot_gui.main
```

Run in background; tell the user to check: theme switching updates the preview, ⛶ opens fullscreen (Esc closes), Settings save doesn't freeze the window, dropping an image with no selection shows the "Select a theme first" dialog.

- [ ] **Step 2: Wait for user feedback; fix anything they report before continuing.**

---

### Task 14: VM capture harness (Part 4, dev-only)

**Files:**
- Create: `test/vm/capture.sh` (executable)

**USER ACTION REQUIRED FIRST:** `sudo apt-get install -y qemu-system-x86 ovmf mtools dosfstools` — pause and ask before this task.

- [ ] **Step 1: Create `test/vm/capture.sh`**:

```bash
#!/usr/bin/env bash
# capture.sh <theme-name> [out.png] - boot real rEFInd with a bundled theme in
# QEMU+OVMF and screenshot the boot menu. DEV TOOL ONLY (not shipped, not CI).
# Requires: qemu-system-x86, ovmf, mtools, dosfstools, imagemagick.
set -euo pipefail
theme="${1:?usage: capture.sh <theme-name> [out.png]}"
repo="$(cd "$(dirname "$0")/../.." && pwd)"
out="${2:-$repo/docs/calibration/$theme.png}"
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT

# 1. find a rEFInd EFI binary (local install, refind package, or apt download)
efi=""
for c in /boot/efi/EFI/refind/refind_x64.efi \
         /usr/share/refind/refind/refind_x64.efi; do
  [ -f "$c" ] && efi="$c" && break
done
if [ -z "$efi" ]; then
  (cd "$work" && apt-get download refind >/dev/null \
    && dpkg-deb -x refind_*.deb x)
  efi="$work/x/usr/share/refind/refind/refind_x64.efi"
fi

# 2. stage ESP contents: rEFInd as the default boot app + theme + manual
#    menu entries (loaders are dummies; rEFInd only needs them to exist)
esp="$work/esp"
mkdir -p "$esp/EFI/BOOT/themes" "$esp/dummy"
cp "$efi" "$esp/EFI/BOOT/BOOTX64.EFI"
cp -r "$repo/themes/$theme" "$esp/EFI/BOOT/themes/$theme"
printf 'x' > "$esp/dummy/linux.efi"
printf 'x' > "$esp/dummy/windows.efi"
cat > "$esp/EFI/BOOT/refind.conf" <<EOF
timeout 0
resolution 1024 768
scanfor manual
include themes/$theme/theme.conf
menuentry "Ubuntu" {
    icon themes/$theme/icons/os_linux.png
    loader /dummy/linux.efi
}
menuentry "Windows" {
    icon themes/$theme/icons/os_win8.png
    loader /dummy/windows.efi
}
EOF

# 3. FAT ESP image via mtools (no mount, no sudo)
img="$work/esp.img"
truncate -s 64M "$img"
mkfs.vfat "$img" >/dev/null
mcopy -i "$img" -s "$esp"/* ::/

# 4. OVMF firmware
ovmf=""
for c in /usr/share/ovmf/OVMF.fd /usr/share/OVMF/OVMF.fd; do
  [ -f "$c" ] && ovmf="$c" && break
done
[ -n "$ovmf" ] || { echo "OVMF.fd not found; install ovmf" >&2; exit 1; }

# 5. boot headless, screendump after rEFInd settles, quit
mkdir -p "$(dirname "$out")"
{ sleep 15; echo "screendump $work/shot.ppm"; sleep 2; echo quit; } | \
  qemu-system-x86_64 -bios "$ovmf" -m 512 \
    -drive file="$img",format=raw,if=ide \
    -display none -serial none -monitor stdio >/dev/null
convert "$work/shot.ppm" "$out"
echo "wrote $out"
```

- [ ] **Step 2: Make executable + run for mac-dark**

```bash
chmod +x test/vm/capture.sh
./test/vm/capture.sh mac-dark
```
Expected: `wrote .../docs/calibration/mac-dark.png`. Read the PNG with the Read tool — it must show the real rEFInd menu with the glass icons. If the screen is still on firmware/splash, increase the `sleep 15`. If rEFInd shows an error banner instead of the menu, read what it says and fix the staged conf accordingly.

- [ ] **Step 3: Run for mac-light**

Run: `./test/vm/capture.sh mac-light`
Expected: `wrote .../docs/calibration/mac-light.png`; verify by reading the image.

- [ ] **Step 4: Commit**

```bash
git add test/vm/capture.sh docs/calibration/
git commit -m "feat(dev): QEMU+OVMF harness capturing real rEFInd screenshots"
```

---

### Task 15: Calibrate compositor against the screenshots (Part 3 ↔ 4)

**Files:**
- Modify: `gui/prettyboot_gui/layout.py` (constants only)
- Create: `docs/calibration/*-compare.png` (side-by-sides)

- [ ] **Step 1: Render compositor output at the same resolution + build side-by-sides**

```bash
cd /home/deva/GitHub/prettyboot/gui
../.venv/bin/python -c "
from prettyboot_gui import preview
for t in ('mac-dark', 'mac-light'):
    preview.render_png(f'../themes/{t}', f'/tmp/sim-{t}.png', 1024, 768)
"
cd ..
for t in mac-dark mac-light; do
  montage "docs/calibration/$t.png" "/tmp/sim-$t.png" \
    -tile 1x2 -geometry +0+4 "docs/calibration/$t-compare.png"
done
```

- [ ] **Step 2: Read each `*-compare.png`** (real on top, simulated below). Compare: vertical position of the big row, gap between the two icons, selection tile size/position, label position/size, small-row position and count. Adjust the constants at the top of `layout.py` (`BIG_ROW_CENTER_Y`, `TILE_GAP`, `LABEL_OFFSET`, `SMALL_ROW_OFFSET`, `SMALL_GAP`, and `n_small` in `preview._paint` if the real tools row has a different count). Re-run Step 1 and re-read. Repeat until the simulated layout visually matches.

- [ ] **Step 3: Run pytest** (invariant tests must still pass after constant tweaks)

Run: `cd gui && ../.venv/bin/python -m pytest tests -q`
Expected: all pass.

- [ ] **Step 4: Send both `*-compare.png` files to the user for the visual gate.** Wait for approval; iterate on feedback.

- [ ] **Step 5: Commit**

```bash
git add gui/prettyboot_gui/layout.py gui/prettyboot_gui/preview.py docs/calibration/
git commit -m "feat(gui): calibrate preview geometry against real rEFInd screenshots"
```

---

### Task 16: Full verification

- [ ] **Step 1: All suites**

```bash
cd /home/deva/GitHub/prettyboot && bats test/ | tail -1
cd gui && ../.venv/bin/python -m pytest tests -q
```
Expected: bats all ok; pytest all pass.

- [ ] **Step 2: Confirm clean tree + log review**

Run: `git status --short && git log --oneline feat/gui-app -20`
Expected: clean tree; one commit per task above.

- [ ] **Step 3: Report to user — ready for the push step** (push method to be decided by user: merge to main vs PR; `.deb` build verification still pending the debhelper install).
