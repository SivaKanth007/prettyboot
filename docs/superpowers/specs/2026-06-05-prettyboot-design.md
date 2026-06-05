# prettyboot — Design Spec

**Date:** 2026-06-05
**Status:** Approved (design), pending implementation

## Goal

`prettyboot` is a small, public, contributor-friendly tool that gives a UEFI
dual-boot PC a graphical, themeable boot picker via **rEFInd**. It is a
**boot-theme manager**: it installs rEFInd, holds a collection of themes, and
lets the user switch the active theme with one command. Anyone can clone it,
install it, and drop in their own theme folders without editing scripts and
without risking an unbootable system.

It ships with a **Mac-style** theme in two variants: `mac-light` (Big Sur frosted
look) and `mac-dark` (Sonoma look).

## Design Principles

- **Align with the existing rEFInd standard.** Each theme is a self-contained
  folder using rEFInd's standard filenames. Any rEFInd theme from the internet
  drops in and works.
- **Foolproof.** Fixed filenames, no fragile suffixes. Validate before applying.
  Never leave the system unbootable.
- **Minimal scripts.** Plain shell, `case` statements, no wrapper functions or
  abstractions beyond what is needed. Easy to read and customize.
- **Nothing hardcoded as policy.** Timeout and active theme are settings changed
  by commands, not source edits.
- **Zero background overhead.** No timers, hooks, or daemons. All actions manual.
- **Vendored assets.** All theme PNGs are committed. Build tools
  (ImageMagick/librsvg) are needed only on the machine that *generates* the mac
  theme, never on a user's machine.

## Implementation Language

**POSIX shell (bash)** for v1. Rationale:

- The tool does thin, infrequent file/package/text-edit operations — no hot loop,
  no long-running process. Compiled-language speed (Go) brings no benefit here.
- Zero dependencies; shell is present on every Linux. Clone and run.
- **Auditability:** the tool runs as root and edits the ESP / `refind.conf`. A
  readable script lets users inspect exactly what touches their boot partition
  before running it — a trust requirement a compiled binary or Node bundle works
  against.
- Genre standard: rEFInd's own installer and most theme installers are shell.

Rejected for v1: **npm/Node** (runtime dependency + black-box for a root/boot
tool) and **Go** (no speed benefit for this workload, per-arch release pipeline,
less auditable). An optional Go TUI front-end is parked in Future Ideas, to be
built only if real demand appears.

## Repo Structure

```
prettyboot/
├── README.md                 # what it is, install, usage, how to add a theme
├── install.sh                # install rEFInd + deploy themes to ESP (sudo)
├── prettyboot.sh             # the manager CLI (sudo): list | use | next | timeout | reset
├── build-assets.sh           # OPTIONAL, build-time only: regenerates the mac themes
├── themes/
│   ├── mac-dark/
│   │   ├── theme.conf
│   │   ├── background.png
│   │   ├── selection_big.png
│   │   ├── selection_small.png
│   │   ├── font.png          # optional
│   │   └── icons/
│   │       ├── os_linux.png
│   │       └── os_win.png
│   └── mac-light/            # same standard layout
└── docs/superpowers/specs/   # this spec
```

## Theme Contract (how anyone adds a theme)

A theme is any folder under `themes/`. To be valid it must contain:

| File / dir            | Required | Purpose                                  |
|-----------------------|----------|------------------------------------------|
| `theme.conf`          | yes      | rEFInd theme config (references the files below by standard name) |
| `background.png`      | yes      | boot screen wallpaper                    |
| `selection_big.png`   | yes      | highlight behind the selected OS icon    |
| `selection_small.png` | yes      | highlight for small/secondary icons      |
| `icons/`              | yes      | OS icons: `os_linux.png`, `os_win.png`, etc. |
| `font.png`            | no       | custom bitmap font; omit to use rEFInd's built-in |

Rules:
- **Filenames are fixed** — no suffixes, no per-theme naming schemes. This is the
  rEFInd standard, so existing community themes are already compatible.
- To add a theme: drop the folder into `themes/`, run `sudo ./prettyboot.sh list`
  to confirm it shows ✓ valid, then `sudo ./prettyboot.sh use <folder-name>`.
- A typo or missing file makes the theme show ✗ in `list` and refuse to activate;
  it never corrupts `refind.conf` or breaks booting.

README documents this table and links rEFInd's official theme documentation.

## CLI: prettyboot.sh

Operates on the deployed copy on the ESP. All commands need `sudo`.

```
sudo ./prettyboot.sh list                # list themes in themes/ with ✓ valid / ✗ broken, mark active
sudo ./prettyboot.sh use <theme>         # validate <theme>, then activate it
sudo ./prettyboot.sh next                # cycle to the next valid theme
sudo ./prettyboot.sh timeout <secs|off>  # set rEFInd timeout (off = 0 = wait forever)
sudo ./prettyboot.sh reset               # remove prettyboot's theme include -> plain rEFInd
```

`use <theme>`:
1. Verify `themes/<theme>/` exists and contains all required files (the contract).
   On failure: print what is missing, change nothing, exit non-zero.
2. Set the active include in `refind.conf` to `include themes/<theme>/theme.conf`
   (replace any prior prettyboot include; keep exactly one).

No light/dark toggle or time-based auto-switch in v1 — explicitly deferred (a
`-light`/`-dark` convention could crash if a paired variant is absent). Switching
between `mac-light` and `mac-dark` is done with `use`, like any other theme.

## install.sh

1. Install rEFInd: `apt-get install -y refind` (non-interactive). If the package
   manager differs, print guidance and exit cleanly.
2. Detect and verify the ESP (commonly `/boot/efi`); confirm it is mounted before
   writing.
3. **Back up** `refind.conf` to `refind.conf.prettyboot.bak` before editing.
4. Copy `themes/` → `<ESP>/EFI/refind/themes/`.
5. Set `timeout 10` (changeable later via `prettyboot.sh timeout`).
6. Activate default theme: `mac-dark`.
7. Print next-step usage.

Multi-PC reuse: `git clone` → `sudo ./install.sh` → `sudo ./prettyboot.sh use ...`
whenever you like.

## Safety / Robustness

- Validation before every activation; broken themes can never be applied.
- `refind.conf` backed up on install; edits are idempotent (re-running does not
  duplicate lines).
- `reset` restores plain rEFInd instantly if a user dislikes a theme.
- rEFInd itself falls back to its built-in appearance if an include is unusable,
  so the menu always renders and the machine stays bootable.

## Assets / build-assets.sh (build-time only)

Generates the two mac themes. Not run by end users.

- **Backgrounds (ImageMagick):** `mac-dark/background.png` = Sonoma radial
  purple→black gradient; `mac-light/background.png` = Big Sur color gradient with
  a frosted rounded panel baked in (live blur is impossible at boot).
- **Icons:** Ubuntu/Linux and Windows logos; SVG sources inline in the script,
  rasterized to `icons/os_linux.png` and `icons/os_win.png` (~128px).
- **Font:** optional bitmap font PNGs (light text for mac-dark, dark text for
  mac-light), recolored from rEFInd's default. If recolor looks poor, omit
  `font.png` and use rEFInd's built-in font; confirm with the user before locking.
- **Selection:** translucent rounded highlight, tuned per variant.

All outputs are committed. `build-assets.sh` is documented as optional.

## Verification

The boot screen can only be fully confirmed by rebooting. Scripts verify what
they can:

- `install.sh`: rEFInd installed, ESP mounted, backup created, theme files copied,
  `refind.conf` has the include + `timeout` lines.
- `prettyboot.sh use`: required files present; `refind.conf` include updated to
  exactly one prettyboot include.
- `prettyboot.sh list`: every theme correctly reported ✓/✗.

User confirms the visual result on next reboot.

## Out of Scope (v1)

- Live blur/translucency at boot (impossible).
- Light/dark toggle and time-based auto-switching (deferred; risk of crash when a
  paired variant is missing).
- Updating appearance based on which OS was used last (would need OS-level hooks).
- Per-OS login avatars/passwords at the boot menu (that is OS login, not boot).
- Bootloaders other than rEFInd; firmware other than UEFI.

## Future Ideas (not committed)

- Optional Go TUI front-end (theme gallery + screenshot preview) calling the same
  logic — only if real demand appears.
- Optional symlink of `prettyboot.sh` to `/usr/local/bin/prettyboot`.
- A safe, opt-in light/dark auto-switch that first checks both variants exist.
- A theme gallery / screenshots in the README.
