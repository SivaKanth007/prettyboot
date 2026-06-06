# prettyboot

A graphical, themeable boot picker for UEFI dual-boot PCs (e.g. Ubuntu + Windows),
built on [rEFInd](https://www.rodsbooks.com/refind/). Ships a Mac-style theme in
light and dark, and lets you switch or add themes with one command — safely.

> **Scope:** UEFI firmware + rEFInd. Themes follow rEFInd's standard layout, so any
> rEFInd theme from the internet drops in and works.

## Install (Ubuntu/Debian)

```bash
sudo add-apt-repository ppa:sivakanth007/prettyboot
sudo apt update
sudo apt install prettyboot
```

This installs both faces of prettyboot:

- **Terminal:** run `prettyboot` for the CLI / interactive menu.
- **Desktop:** search "prettyboot" in your apps to open the GUI.

On first launch, click **Set up boot menu** to deploy themes and enable
rEFInd. Updates arrive automatically through `apt upgrade`.

## GUI

The app has three tabs: **Themes** (switch + full-size live preview +
drag-drop import), **Settings** (curated, validated options), and
**Advanced** (raw `refind.conf` with automatic backup).

## Install from source

```bash
git clone https://github.com/SivaKanth007/prettyboot
cd prettyboot
sudo ./install.sh
```

This installs rEFInd (via apt), deploys the bundled themes, backs up your existing
`refind.conf`, sets the boot-menu timeout to 10 seconds, and activates `mac-dark`.
Reboot to see it.

## Usage

After install, just run the interactive menu:

```bash
sudo prettyboot                          # opens a menu: choose theme, set timeout, reset
```

Or use the individual commands directly (also scriptable):

```bash
sudo ./prettyboot.sh list                # list themes (* active, ✓ valid, ✗ broken)
sudo ./prettyboot.sh use mac-light       # activate a theme
sudo ./prettyboot.sh use mac-dark
sudo ./prettyboot.sh next                # cycle to the next valid theme
sudo ./prettyboot.sh timeout off         # menu waits forever (off = 0 = no auto-boot)
sudo ./prettyboot.sh timeout 10          # auto-boot default after 10s
sudo ./prettyboot.sh reset               # remove prettyboot settings -> plain rEFInd
```

## Adding your own theme

A theme is a folder under `themes/` using rEFInd's standard filenames:

| File / dir            | Required | Purpose                                   |
|-----------------------|----------|-------------------------------------------|
| `theme.conf`          | yes      | rEFInd theme config                       |
| `background.png`      | yes      | boot screen wallpaper                     |
| `selection_big.png`   | yes      | highlight behind the selected OS icon     |
| `selection_small.png` | yes      | highlight for small icons                 |
| `icons/`              | yes      | OS icons: `os_linux.png`, `os_win.png`, … |
| `font.png`            | no       | custom bitmap font (else rEFInd built-in) |

Steps:
1. Drop your folder into `themes/your-theme/`.
2. `sudo ./prettyboot.sh list` — confirm it shows `✓`.
3. `sudo ./prettyboot.sh use your-theme`, then reboot.

A missing or misspelled file makes the theme show `✗` and refuse to activate — it
never corrupts `refind.conf` or breaks booting. See the
[rEFInd theme docs](https://www.rodsbooks.com/refind/themes.html) for `theme.conf`
options.

## Safety

- Your original `refind.conf` is backed up to `refind.conf.prettyboot.bak` on install.
- Themes are validated before activation; broken themes are never applied.
- `sudo ./prettyboot.sh reset` restores plain rEFInd instantly.

## Regenerating the Mac theme (maintainers)

The Mac theme PNGs are committed (vendored). To regenerate or tweak them:

```bash
sudo apt-get install -y imagemagick librsvg2-bin
./build-assets.sh
```

## Development

```bash
sudo apt-get install -y bats
bats test/
```

Scripts are plain bash; `lib.sh` holds shared helpers. All scripts honor
`REFIND_DIR` (default `/boot/efi/EFI/refind`) so tests run against temp dirs.

## Roadmap

- Optional desktop app (drag-and-drop themes, icon editing), packaged as
  `.deb`/AppImage/Flatpak, wrapping this shell core.
- Opt-in light/dark auto-switch (only when both variants exist).

## License

MIT — see [LICENSE](LICENSE).
