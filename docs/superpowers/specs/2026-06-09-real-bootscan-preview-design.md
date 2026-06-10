# prettyboot: Real Boot-Scan Preview — Design

Date: 2026-06-09
Status: Approved

## Goal

Make the GUI preview an exact replica of the user's actual rEFInd boot screen by
sourcing the real boot entries and tools row from the system, instead of the
simulated two-entry menu. Ground truth: the user's photos of their physical
boot menu (4 entries: Windows selected, Ubuntu, unknown-OS, Ubuntu-fallback;
6 tools: MOK key, about, hidden-tags, shutdown, reboot, firmware; label
"Boot Microsoft EFI boot from SYSTEM").

Approach chosen: **real boot scan + real icons in the existing compositor**
(rejected: QEMU live render in-app — heavy user dependency, slow; hybrid —
extra path for marginal gain).

## Facts from the user's machine (verified)

- ESP mounted world-readable at `/boot/efi`; partition label `SYSTEM`.
- Loaders: `EFI/Microsoft/Boot/bootmgfw.efi`, `EFI/ubuntu/{shimx64,grubx64,mmx64}.efi`,
  `EFI/Boot/{bootx64,fbx64,mmx64}.efi`, `EFI/refind/refind_x64.efi`.
- rEFInd's own icon PNGs readable at `/boot/efi/EFI/refind/icons/`
  (`os_unknown.png`, `func_about.png`, `func_hidden.png`, `func_shutdown.png`,
  `func_reset.png`, `func_firmware.png`, `tool_mok_tool.png`, …).
- Real menu shows 4 big entries — `mm*.efi` (MokManager) are NOT entries
  (they enable the mok_tool instead); `grubx64.efi` is not shown separately
  when shim is present in the same directory.

## Part 1 — `gui/prettyboot_gui/bootscan.py` (new, pure)

`scan_entries(efi_root: str, refind_dir: str, volume: str) -> list[dict]`
- Walk `efi_root` one directory level deep (`EFI/<dir>/*.efi`, plus nested
  `Boot` subdirs like `Microsoft/Boot`), case-insensitive `.efi` match.
- Skip: rEFInd's own directory (the one containing `refind_x64.efi` /
  matching `refind_dir`), tool binaries (`mm*.efi`, `mokmanager*.efi`,
  `fb*.efi` is KEPT — the user's photo shows it as the unknown-OS entry),
  and `grub*.efi` when a `shim*.efi` exists in the same directory
  (mirrors what the user's real menu shows).
- Each entry: `{"label": str, "icon": str}` where icon is an absolute path:
  - dir or file contains `microsoft`/`bootmgfw` → `<theme>/icons/os_win8.png`
    (theme dir passed by the caller via icon resolution callback — see
    integration; bootscan returns a semantic key instead: `"win"`,
    `"linux"`, `"unknown"`), label `Boot Microsoft EFI boot from <volume>`.
  - dir or file contains `ubuntu`/`shim`/`grub` → key `"linux"`, label
    `Boot ubuntu from <volume>` (dir name).
  - otherwise → key `"unknown"`, label `Boot <filename> from <volume>`.
- Ordering: match rEFInd's observed order on the user's machine —
  `Microsoft` first, then `ubuntu`, then `Boot` fallback entries (sort
  key: Microsoft < named dirs < Boot). Acceptance is the photo comparison.
- Pure: no subprocess; `volume` is a parameter.

`scan_tools(efi_root: str, refind_dir: str) -> list[str]`
- Ordered candidate list of (condition, icon filename in `refind_dir/icons/`):
  1. mok_tool — `tool_mok_tool.png` — when any `mm*.efi`/`mokmanager*.efi`
     exists under `efi_root`.
  2. shell — `tool_shell.png` — when `shellx64.efi`/`EFI/tools/shell*.efi`
     exists.
  3. about — `func_about.png` — always.
  4. hidden-tags — `func_hidden.png` — always.
  5. shutdown — `func_shutdown.png` — always.
  6. reboot — `func_reset.png` — always.
  7. firmware — `func_firmware.png` — always.
- Include an icon only if the PNG file actually exists; return absolute paths.

`volume_label(mountpoint: str) -> str`
- The one impure helper: `findmnt -no SOURCE <mountpoint>` then
  `lsblk -no LABEL <dev>`; returns `""` on any failure. Lives in bootscan
  but isolated so tests can inject the label directly into `scan_entries`.

## Part 2 — `preview.py` integration

In `_load_assets(theme_dir)`:
- Derive `refind_dir = dirname(dirname(theme_dir))` (theme lives at
  `<refind_dir>/themes/<name>`) and `efi_root = dirname(refind_dir)`.
- If `efi_root` basename is `EFI` and is a readable directory: run
  `scan_entries` (volume from `volume_label` of `dirname(efi_root)`) and
  `scan_tools`. Resolve semantic icon keys: `win` → theme `os_win8.png`
  (falls back to `os_win.png`), `linux` → theme `os_linux.png`, `unknown` →
  `refind_dir/icons/os_unknown.png`.
- On any failure, unreadable dir, or empty entry list: **fall back to the
  current simulated preview** (collapsed theme icon pair, "Ubuntu"/"Windows"
  labels, outline-square tools). Sandbox GUI and tests keep working.
- `assets["entries"]` becomes `[(label, surface)]` (label now a full string,
  not a filename key); `assets["tools"]` = list of tool surfaces (or `None`
  marker list for the fallback outline squares).
- `_paint`: `n_big = len(entries)`, `n_small = len(tools)`; label drawn from
  the entry's label string; tools drawn as real scaled PNGs when surfaces
  exist, outline squares otherwise. Selected = 0 (rEFInd default highlights
  the first entry).

## Part 3 — `app.py`

No changes. `build_widget(theme_dir)` contract unchanged; the real scan keys
off the theme path already passed in.

## Part 4 — Tests & acceptance

- pytest `gui/tests/test_bootscan.py` (pure, fake ESP tree in tmp_path):
  - Windows/ubuntu/unknown classification and label format.
  - rEFInd's own dir skipped; `mm*.efi` excluded from entries but enables
    mok_tool; `grub*` suppressed when shim present in same dir; `fb*.efi`
    kept as unknown.
  - `scan_tools` ordering and exists-filtering.
- preview tests: fallback path still renders (existing `test_render_png`
  covers it — tmp theme has no `EFI` ancestor); add a test rendering with a
  fake ESP + fake icons proving real entries/tools are used (count via
  layout or just that render succeeds with 4 entries).
- **Acceptance gate:** render the active theme at the user's resolution and
  compare side-by-side with the photos in `/home/deva/Downloads/Boot_Menu/`;
  user approves visually. Expected remaining difference: font only.

## Out of scope

- Reimplementing rEFInd's full scanner (NVRAM entries, multi-volume scans,
  hidden-tags state, BIOS/legacy entries).
- QEMU-based live rendering in the app.
- Keyboard navigation/selection simulation in the preview.
