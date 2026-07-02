# README media (images + animations) — design

Date: 2026-07-02
Status: approved

## Goal

Give the README visual previews: boot-menu stills, an animated boot-menu GIF,
GUI screenshots, and a CLI demo GIF.

## Approach

Reuse the GUI's own headless renderer `gui/prettyboot_gui/preview.render_png()`
(calibrated against QEMU screenshots) for boot-menu stills and GIF frames.
Rejected alternatives: hand-compositing with ImageMagick (duplicates layout
logic, drifts from truth) and QEMU screenshots (heavy, slow).

## Assets — all committed under `docs/media/`

| File | How |
|------|-----|
| `preview-mac-dark.png`, `preview-mac-light.png` | `render_png` at 1024×768 |
| `boot-menu.gif` | `render_png` frames cycling `selected` 0↔1 and dark↔light; ImageMagick assembles; ≤ ~3 MB |
| `gui-themes.png` | real GUI launched with `GDK_BACKEND=x11`, captured via ImageMagick `import` |
| `cli-demo.gif` | asciinema + agg recording of scripted `prettyboot.sh list/use/next` against a temp `REFIND_DIR` |
| `build-media.sh` | regen script mirroring `build-assets.sh` pattern |

## README placement

- Hero: `boot-menu.gif` directly under the intro paragraph.
- New "Themes" section near the top: dark/light stills side by side (HTML table).
- GUI section: `gui-themes.png`.
- Usage section: `cli-demo.gif`.

## Out of scope

No changes to theme assets, GUI code, or CLI behavior.
