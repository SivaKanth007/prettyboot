# custom-boot — Design Spec

**Date:** 2026-06-05
**Status:** Approved (design), pending implementation

## Goal

A git repo that turns a UEFI Ubuntu + Windows dual-boot PC into a graphical,
Mac-styled boot picker using rEFInd. The repo is a small **boot-theme manager**:
it holds multiple themes, lets you switch the active theme/skin manually anytime,
and is reusable across multiple PCs by cloning + running one install script.

First theme shipped: **mac** (Big Sur frosted light skin + Sonoma dark skin).

## Constraints / Decisions

- **Bootloader:** rEFInd (UEFI). Lowest risk, themeable, multi-PC friendly.
- **Look:** Mac-style. Achievable: background PNG, icon row, selection highlight,
  font. NOT achievable at boot: live blur/translucency — frost is baked into the
  static wallpaper PNG.
- **No timeout:** rEFInd `timeout 0` — menu waits forever, never auto-boots,
  stays until the user selects an OS.
- **Light/dark:** one theme, two skins. Skins differ in 4 files only.
- **Switch is MANUAL only.** No timers, no systemd hooks, no login hooks, no
  Windows scheduled tasks. Zero background overhead on either OS.
- **Expandable:** adding a theme = drop a folder following the file-naming
  contract. No script edits required.
- **Minimal scripts:** plain shell, `case` statements, no functions/classes/
  wrappers beyond what is strictly needed. Easy to edit later.
- **Vendored assets:** all PNGs committed to the repo. Target PCs never generate
  anything. Image tools (ImageMagick/librsvg) are build-machine only.

## Repo Structure

```
custom-boot/
├── README.md                     # what it is, install steps, switch usage, theme contract
├── install.sh                    # install rEFInd + deploy themes to ESP (sudo)
├── boot-theme.sh                 # manual switch (sudo)
├── build-assets.sh               # OPTIONAL, build-time only: regenerates mac PNGs
└── themes/
    └── mac/
        ├── theme.conf            # rEFInd layout for this theme
        ├── os_ubuntu.png         # icons, shared by both skins
        ├── os_win.png
        ├── background.dark.png   background.light.png
        ├── font.dark.png         font.light.png
        ├── selection_big.dark.png    selection_big.light.png
        └── selection_small.dark.png  selection_small.light.png
```

No `skins/`, `icons/`, `assets-src/`, or `_TEMPLATE/` folders. Skin identity is a
filename suffix (`.dark` / `.light`). One folder per theme.

## Theme Contract (expandability)

A theme is any folder under `themes/`. To be valid it must contain:

- `theme.conf` — rEFInd theme include file. References the **active** (un-suffixed)
  asset names: `background.png`, `font.png`, `selection_big.png`,
  `selection_small.png`, and the icon files.
- Icon PNGs: `os_ubuntu.png`, `os_win.png` (shared across skins).
- For each skin `<s>`: `background.<s>.png`, `font.<s>.png`,
  `selection_big.<s>.png`, `selection_small.<s>.png`.

A theme with a single look still uses one skin suffix (e.g. `.default`).
`boot-theme.sh` discovers themes by listing `themes/*/` and discovers skins by
parsing `background.*.png` suffixes. No script changes to add a theme.

## How the Manual Switch Works

`boot-theme.sh` operates on the deployed copy on the ESP
(`/boot/efi/EFI/refind/themes/`). Commands:

```
sudo ./boot-theme.sh list            # list discovered themes + skins
sudo ./boot-theme.sh use <theme> <skin>
sudo ./boot-theme.sh toggle          # flip current theme between light/dark
sudo ./boot-theme.sh auto            # choose skin by current hour, only when run
```

`use <theme> <skin>` does two things:
1. Copy `background.<skin>.png → background.png` and the same for `font` and the
   two `selection` files, inside `themes/<theme>/` on the ESP.
2. Set the active include in `refind.conf` to `include themes/<theme>/theme.conf`.

`use` writes the chosen skin name to a one-line marker file
`themes/<theme>/.current-skin` on the ESP. `toggle` reads that marker and
switches light↔dark (defaulting to dark if absent). `auto` picks `light` for
daytime hours and `dark` otherwise, then calls the same copy logic — but only at
the moment the user runs it.

## install.sh

1. Install rEFInd (`apt-get install -y refind`, non-interactive).
2. Copy `themes/` → `/boot/efi/EFI/refind/themes/`.
3. Configure `refind.conf`: set `timeout 0`, set `include` to `mac/theme.conf`,
   set default boot to the Ubuntu/Windows entries as rEFInd auto-detects them.
4. Activate default skin: `dark`.

Multi-PC reuse: `git clone` → `sudo ./install.sh` → optionally
`sudo ./boot-theme.sh use ...` later.

ESP path is detected (commonly `/boot/efi`); script verifies it is mounted and is
the EFI System Partition before writing.

## Assets / build-assets.sh (build-time only)

- **Backgrounds:** generated with ImageMagick.
  - `background.dark.png`: Sonoma-style radial purple→black gradient.
  - `background.light.png`: Big Sur-style color gradient with a frosted rounded
    panel baked in.
- **Icons:** Ubuntu and Windows logos, SVG sources inline in the script,
  rasterized to PNG (~128px). Shared by both skins.
- **Font:** rEFInd uses baked-color bitmap font PNGs. `font.dark.png` = light
  text, `font.light.png` = dark text, recolored from rEFInd's default font.
  Fallback: if recolor looks bad, use rEFInd's built-in font (good on dark,
  acceptable on light) and confirm with the user before finalizing.
- **Selection:** translucent rounded highlight; light + dark variants.

All outputs are committed (vendored). `build-assets.sh` is documented as optional
and only needed to regenerate or tweak the mac theme.

## Verification

Boot-screen appearance can only be fully confirmed by rebooting. Scripts verify
what they can:

- `install.sh`: rEFInd binary installed, ESP mounted, theme files copied,
  `refind.conf` contains the `include` and `timeout 0` lines.
- `boot-theme.sh`: target theme/skin files exist before switching; active asset
  files updated; `refind.conf` include line updated.

User confirms the visual result on next reboot.

## Out of Scope (v1)

- Live blur/translucency at boot (not possible).
- Auto skin switching by time without user action (would need OS-level hooks;
  explicitly rejected to keep zero overhead).
- Updating the skin when the previous session was Windows (Windows-side task;
  could be added later).
- Per-OS login avatars/password at the boot menu (that is OS login, not boot).
