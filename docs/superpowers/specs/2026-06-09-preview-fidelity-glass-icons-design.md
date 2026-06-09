# prettyboot: Preview Fidelity, Glass Icons, and Bug Fixes — Design

Date: 2026-06-09
Status: Approved

## Goal

Three improvements to the prettyboot GUI (built on branch `feat/gui-app`):

1. Fix the bugs found in the post-build audit.
2. Replace the flat Windows/Ubuntu theme icons with a consistent "glassmorphism"
   icon set (translucent layered shapes, gradient sheen — Microsoft
   Authenticator-style), authored as SVGs in-repo and rendered by the existing
   asset pipeline. Same style supplies the missing desktop app icon.
3. Make the in-app theme preview visually match what rEFInd actually renders at
   boot, validated against ground-truth screenshots captured from a real rEFInd
   boot inside a QEMU+OVMF virtual machine ("VM-calibrated compositor").

## Decisions made

- **Preview approach: VM-calibrated compositor.** QEMU/OVMF is a development
  tool only; end users get an instant, zero-dependency preview whose layout
  math was tuned to match real screenshots. (Rejected: live VM render in-app —
  heavy user dependency; compositor without calibration — unverified; shipped
  pre-rendered screenshots — no preview for imported themes.)
- **Icon approach: author glass SVGs in-repo.** Rendered via the existing
  `build-assets.sh` (rsvg-convert + ImageMagick, both already installed).
  (Rejected: downloading icon packs — licensing per pack; external AI
  generation — no image-gen tool available here, inconsistent style.)
- **Icon scope: replace icons in the bundled `mac-dark` and `mac-light`
  themes.** No new theme variants.

## Part 1 — Bug fixes

| # | Location | Fix |
|---|----------|-----|
| 1 | `gui/prettyboot.desktop` / packaging | Ship an actual app icon: glass `prettyboot` SVG rendered to PNG, installed to `/usr/share/icons/hicolor/256x256/apps/prettyboot.png` via `debian/install`. Fixes the dangling `Icon=prettyboot` reference. |
| 2 | `gui/prettyboot_gui/engine.py` `import_path` | When a zip extracts to a single top-level directory, import that directory regardless of whether `name` was passed (current code imports the extraction root when `name` is set, producing a broken theme). |
| 3 | `gui/prettyboot_gui/engine.py` `_write` | Capture stderr (`capture_output=True`); on failure raise with stderr text so the GUI error dialog shows the actual reason, not just an exit code. |
| 4 | `gui/prettyboot_gui/app.py` `_run` | Run write operations off the GTK main thread (worker thread + `GLib.idle_add` for UI updates) so the window does not freeze while pkexec shows its password prompt. |
| 5 | `gui/prettyboot_gui/app.py` | Hide the "Set up boot menu" banner after setup succeeds. |
| 6 | `gui/prettyboot_gui/engine.py` `write_conf` | Create the temp file with 0600 permissions and delete it after the write completes. |
| 7 | `gui/prettyboot_gui/app.py` `_on_bg_drop` | Dropping a background with no theme selected shows feedback ("select a theme first") instead of silently doing nothing. |
| 8 | `gui/prettyboot_gui/app.py` | Add the fullscreen ⛶ button on the preview (promised in the original GUI spec, never implemented). Toggles a fullscreen view of the preview widget. |
| 9 | git | Commit the pending `REFIND_DIR = os.environ.get(...)` fix in `app.py`. |

## Part 2 — Glass icon set

- New `assets/` SVG sources, one consistent glass style:
  - `os_win.svg` — Windows four-pane mark, glass treatment.
  - `os_ubuntu.svg` — Ubuntu circle-of-friends mark, glass treatment.
  - `prettyboot.svg` — app icon for the desktop entry.
- Glass construction (pure SVG, no external assets): rounded-square or free
  shape base with translucent layered fills, linear/radial gradient sheen,
  Gaussian-blur specular highlight, soft drop shadow. Dark and light theme
  variants if needed for contrast against the two backgrounds.
- `build-assets.sh` gains a step that renders these SVGs to PNG:
  - `os_win.png` + `os_win8.png` (identical copies — rEFInd tag matching) and
    `os_ubuntu.png` + `os_linux.png` into **both** `themes/mac-dark/icons/`
    and `themes/mac-light/icons/`, replacing the current flat icons.
  - Big-icon size 128×128 (rEFInd default `big_icon_size`).
  - `prettyboot.png` 256×256 for the hicolor icon dir.
- Rendered PNGs stay vendored (committed), same as today; the SVGs make them
  reproducible and tweakable.
- Trademark note: nominative use of OS marks as boot icons, same practice as
  rEFInd's own bundled icons.

## Part 3 — Preview compositor v2

Replace the current approximate preview (background + centered icon row) in
`gui/prettyboot_gui/preview.py` with a renderer that reproduces rEFInd's real
boot-screen layout.

- **Architecture: pure layout + cairo drawing.**
  - `layout(resolution, entries, theme_conf) -> dict` — pure, testable
    function returning pixel rectangles for: background, each big entry icon,
    the `selection_big` highlight position, the small/tools row,
    `selection_small`, and the entry label text baseline. Uses rEFInd's actual
    geometry rules (big row horizontally centered, vertical placement, row
    spacing, selection image centered behind the selected entry).
  - `draw(cairo_ctx, layout, assets)` — paints onto a `Gtk.DrawingArea` whose
    virtual canvas is the configured resolution (default 1920×1080 or the
    `resolution` setting), scaled to fit the widget. This keeps all layout math
    in real boot-screen pixels.
- **theme.conf parsing (subset honored):** `selection_big`, `selection_small`,
  `banner`, `hideui` flags (e.g. `label`, `singleuser`, `tools`), text color
  if specified. Unknown directives ignored.
- **Entries simulated:** one Linux entry + one Windows entry (the dual-boot
  case prettyboot targets) plus the small tools row, so the preview shows the
  selection highlight on a realistic menu.
- The existing `theme_assets()` helper stays; `build_widget()` keeps its
  signature so `app.py` changes are minimal (plus the new fullscreen button).

## Part 4 — VM calibration harness (dev-only)

- `test/vm/capture.sh`:
  1. Builds a FAT ESP disk image containing rEFInd (EFI binary copied from the
     local install at `$REFIND_DIR` or fetched via `apt download refind`), a
     theme, and a minimal `refind.conf` including that theme.
  2. Boots `qemu-system-x86_64` with OVMF firmware, headless
     (`-display none -monitor stdio`).
  3. Issues `screendump` to capture the boot menu as PPM, converts to PNG.
  4. Output: one screenshot per bundled theme under `docs/calibration/`.
- Prerequisite (user action, once): `sudo apt install qemu-system-x86 ovmf`.
- Calibration loop: compare QEMU screenshot vs compositor output side by side,
  adjust the `layout()` constants until they visually match. Screenshots are
  committed as the fidelity record.
- Not shipped in the .deb; not run in CI.

## Part 5 — Testing

- **pytest (gui/tests/):**
  - Layout math: `layout()` positions for given resolution/entry-count
    (centering, selection rect equals selected icon center, small row below).
  - Zip-import fix: zip with single top folder + explicit name imports the
    inner folder.
  - `_write` failure surfaces stderr text in the raised exception.
- **bats:** existing 43 tests stay green; no CLI behavior changes expected.
- **Visual gate:** side-by-side QEMU screenshot vs compositor preview reviewed
  and approved by the user before push.

## Execution order

1. Bug fixes (Part 1) — small, independent, unblocks everything.
2. Glass icons (Part 2) — user reviews the look in the GUI.
3. VM harness (Part 4) — needs the one-time qemu/ovmf install.
4. Compositor + calibration (Part 3, using Part 4's screenshots).
5. Final visual approval → commit, push.

## Out of scope

- Live VM rendering inside the shipped app.
- New theme variants beyond mac-dark/mac-light.
- Font rendering fidelity (rEFInd bitmap font reproduction) beyond a plain
  label approximation.
- CI automation of the VM capture.
