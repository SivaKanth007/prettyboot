# prettyboot GUI — Design Spec

**Date:** 2026-06-05
**Status:** Approved, ready for implementation planning

## Goal

Add a graphical desktop app to prettyboot so users can manage their rEFInd
boot menu — switch themes, set options, drag-and-drop import themes, edit
icons/backgrounds, and edit raw config — without the terminal. Ship it
alongside the existing CLI in a single `.deb`, distributed via a Launchpad PPA
so `apt` handles installation and updates.

After `sudo apt install prettyboot`:
- running `prettyboot` in a terminal opens the CLI (today's tool, unchanged),
- searching "prettyboot" in the apps list launches the GUI.

Both drive the same engine.

## Non-Goals (v1)

- No reimplementation of boot-config logic in Python — the bash engine stays
  the single source of truth.
- No exposure of rEFInd settings that can't be validated safely as curated
  controls (those live only in the Advanced raw editor).
- No silent boot-partition changes during package install.
- No cross-distro packaging beyond Debian/Ubuntu `.deb` + PPA.

## Architecture

One repo, one package (`prettyboot`, arch `all`). The GUI is a thin frontend;
every write to the boot config goes through the existing bash CLI.

```
prettyboot/
  lib.sh prettyboot.sh install.sh   engine — calls unchanged except new subcommands
  themes/                            bundled mac-dark / mac-light
  gui/
    prettyboot_gui/                  Python GTK4 application package
    prettyboot.desktop               apps-list entry → launches the GUI
    com.prettyboot.policy            polkit policy for privileged ops
  debian/                            .deb packaging
  docs/superpowers/specs/            this spec
  test/                              bats tests (engine + new subcommands)
```

**Layering rule:** GUI's only genuinely new code is presentation + drag-drop
import + live preview + settings widgets. Activating themes, setting timeout,
importing, and config edits all shell out to the CLI. No boot-config logic is
duplicated in Python.

**Tech stack:** Python 3 + GTK4 (PyGObject). Native Ubuntu look, follows
system light/dark, built-in drag-drop (`Gtk.DropTarget`), no compile step.

**Privilege handling:** the GUI runs as the normal user. Any operation that
writes to the ESP / `refind.conf` is executed via `pkexec prettyboot <args>`,
producing a single polkit password prompt. The full GUI never runs as root.

## UI

A single window with three tabs: **Themes**, **Settings**, **Advanced**.

### Themes tab (layout A — full-size preview)

- **Left rail (slim):** list of installed themes (active one marked); a
  drop zone for importing; a timeout dropdown; an **Apply** button.
- **Main area:** a large 16:9 **live preview** rendering the selected theme's
  actual `background.png` + OS icons + selection box at true boot proportions.
  A **⛶** button pops the preview to genuine fullscreen to show exactly what
  boot looks like.
- Selecting a theme updates the preview; **Apply** activates it
  (`pkexec prettyboot use <name>`).

### Settings tab (curated, validated)

Dropdowns/toggles only — no free-text that could produce a bad value:
- Default OS (`default_selection`)
- Timeout
- Screen resolution
- Show tools (`showtools`)
- Hide UI elements (`hideui`)

These persist into prettyboot's managed block in `refind.conf` through a new
generic CLI command (`prettyboot set <key> <value>`), so the engine owns the
write and the backup.

### Advanced tab

Raw `refind.conf` in a text editor. On save: write a timestamped backup, then
`pkexec` the write. Warns if the user removed the
`# >>> prettyboot >>>` / `# <<< prettyboot <<<` markers (the GUI relies on
them to locate its block).

## Flows

### Drag-drop import (folder or .zip)

1. User drops a folder or `.zip` on the left rail.
2. App copies to a temp dir (unzips if needed).
3. Validates against the theme contract using the engine's existing
   `pb_validate_theme` (same check the CLI uses): requires `theme.conf`,
   `background.png`, `selection_big.png`, `selection_small.png`, `icons/`.
4. **Valid** → prompt for a name (defaults to folder name) →
   `pkexec prettyboot import <dir> <name>` installs into the ESP `themes/`
   directory; the theme appears in the list.
5. **Invalid** → red banner listing exactly what is missing; nothing is
   written.

### Theme editor (edit icons / background)

- Select theme → **Edit** → drop a replacement `background.png` or any
  `os_*.png`; the live preview updates immediately.
- **Save** → `pkexec` writes the swapped files. Automatically keeps the
  `os_win` = `os_win8` and `os_linux` = `os_ubuntu` duplicate pairs in sync
  (rEFInd needs both names; FAT32 ESP has no symlinks).
- Editing a bundled mac theme warns "this changes the shipped theme" and
  offers **Save as copy**.

### First-run boot setup

`apt install` places the app but does **not** touch the boot partition
(silent ESP changes in a package postinst are unsafe and would fail on
non-rEFInd machines). On first launch the GUI shows a **"Set up boot menu"**
button that runs the existing `install.sh` logic via `pkexec` (install rEFInd
if absent, back up `refind.conf`, deploy bundled themes, set defaults). Boot
changes only happen on the user's explicit click.

## New CLI subcommands (engine)

Added to keep all boot-config writes in the engine:

- `prettyboot import <dir> [name]` — validate a theme dir and copy it into
  `themes/`.
- `prettyboot set <key> <value>` — write a curated setting into the managed
  block.
- `prettyboot get <key>` — read a curated setting (for populating the UI).

These reuse existing helpers (`pb_validate_theme`, `pb_block_get`,
`pb_block_write`, `pb_deploy_themes`).

## Packaging & distribution

- `debian/` produces package `prettyboot`, arch `all`.
- Runtime depends: `python3`, `python3-gi`, `gir1.2-gtk-4.0`, `policykit-1`,
  `refind`.
- File layout:
  - `/usr/share/prettyboot/` — engine, GUI module, bundled themes
  - `/usr/bin/prettyboot` — CLI entry
  - `/usr/share/applications/prettyboot.desktop` — GUI launcher
  - `/usr/share/polkit-1/actions/com.prettyboot.policy` — polkit policy
- **Distribution:** Launchpad PPA (`ppa:sivakanth007/prettyboot`). Users:
  `add-apt-repository`, then `apt install`; updates come via normal
  `apt upgrade`. Requires a Launchpad account + signing key (one-time, user
  action). `debian/changelog` drives versions.

## Testing

- New CLI subcommands (`import`, `set`, `get`) get bats tests alongside the
  existing suite, using the `REFIND_DIR` override and temp dirs.
- GUI kept thin (logic lives in the CLI), so it gets a launch/smoke test only.
- `.deb` validated with `lintian` and an install-in-container check.

## Known rEFInd limitations (carried forward)

The GUI cannot work around what rEFInd itself can't do: text color is
auto-chosen by background brightness, the menu can't be repositioned, and the
OEM/Windows boot logo can't be restored on chainload. The curated Settings
tab will not offer controls that promise these.
