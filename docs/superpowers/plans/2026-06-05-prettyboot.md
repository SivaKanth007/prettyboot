# prettyboot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `prettyboot`, a shell-based rEFInd boot-theme manager that installs rEFInd, ships a Mac-style theme in light/dark, and lets users switch/add themes safely from one command — then publish it as a public GitHub repo.

**Architecture:** A small POSIX/bash codebase. `lib.sh` holds pure file-operation helpers (theme validation, refind.conf managed-block editing, theme discovery, deploy). `prettyboot.sh` is the user CLI (`list`/`use`/`next`/`timeout`/`reset`) that wires those helpers. `install.sh` installs rEFInd and deploys themes. `build-assets.sh` regenerates the Mac theme PNGs (build-time only). All scripts read `REFIND_DIR` (default `/boot/efi/EFI/refind`) so tests run against temp dirs with no root or real boot partition.

**Tech Stack:** bash, awk, bats-core (tests), ImageMagick + librsvg (asset generation only), gh (publish).

---

## File Structure

```
prettyboot/
├── README.md                 # usage, theme contract, dev/testing
├── LICENSE                   # MIT
├── .gitignore
├── lib.sh                    # pb_* shared helpers (sourced)
├── prettyboot.sh             # CLI: list|use|next|timeout|reset
├── install.sh                # install rEFInd + deploy + default theme
├── build-assets.sh           # regenerate mac-dark/mac-light PNGs (build-time)
├── themes/
│   ├── mac-dark/{theme.conf,background.png,selection_big.png,selection_small.png,icons/{os_linux.png,os_win.png}}
│   └── mac-light/{...same...}
├── test/
│   ├── helper.bash           # shared test setup (make_theme)
│   ├── lib.bats              # unit tests for lib.sh
│   ├── cli.bats              # tests for prettyboot.sh
│   ├── install.bats          # test for install.sh deploy/block logic
│   └── build.bats            # test for build-assets.sh (gated on tools)
└── docs/superpowers/{specs,plans}/
```

**Managed-block format** (written into `refind.conf`):
```
# >>> prettyboot >>>
timeout 10
include themes/mac-dark/theme.conf
# <<< prettyboot <<<
```
Exactly one block; rewritten wholesale on every change; removed by `reset`. This is the single source of truth for active theme + timeout.

---

## Task 1: Scaffold repo + test harness

**Files:**
- Create: `.gitignore`, `LICENSE`, `test/helper.bash`

- [ ] **Step 1: Install bats (test runner)**

Run: `sudo apt-get install -y bats`
Expected: bats installed; `bats --version` prints a version.

- [ ] **Step 2: Create `.gitignore`**

```
*.tmp
*.bak
refind.conf.prettyboot.bak
```

- [ ] **Step 3: Create `LICENSE` (MIT)**

```
MIT License

Copyright (c) 2026 SivaKanth007

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 4: Create `test/helper.bash`**

```bash
# Shared test helpers.

# make_theme <themes_dir> <name>  -- create a fully valid theme folder
make_theme() {
  mkdir -p "$1/$2/icons"
  : > "$1/$2/theme.conf"
  : > "$1/$2/background.png"
  : > "$1/$2/selection_big.png"
  : > "$1/$2/selection_small.png"
  : > "$1/$2/icons/os_linux.png"
  : > "$1/$2/icons/os_win.png"
}
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore LICENSE test/helper.bash
git commit -m "chore: scaffold prettyboot repo and test harness

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: lib.sh — theme validation + discovery

**Files:**
- Create: `lib.sh`
- Test: `test/lib.bats`

- [ ] **Step 1: Write the failing tests**

`test/lib.bats`:
```bash
load helper

setup() { TMP="$(mktemp -d)"; . "$BATS_TEST_DIRNAME/../lib.sh"; }
teardown() { rm -rf "$TMP"; }

@test "valid theme passes validation" {
  make_theme "$TMP/themes" mac-dark
  run pb_validate_theme "$TMP/themes" mac-dark
  [ "$status" -eq 0 ]
}

@test "missing required file fails validation" {
  make_theme "$TMP/themes" mac-dark
  rm "$TMP/themes/mac-dark/background.png"
  run pb_validate_theme "$TMP/themes" mac-dark
  [ "$status" -eq 1 ]
  [[ "$output" == *background.png* ]]
}

@test "unknown theme fails validation" {
  run pb_validate_theme "$TMP/themes" nope
  [ "$status" -eq 1 ]
}

@test "list_theme_names returns sorted names" {
  make_theme "$TMP/themes" zeta
  make_theme "$TMP/themes" alpha
  run pb_list_theme_names "$TMP/themes"
  [ "${lines[0]}" = "alpha" ]
  [ "${lines[1]}" = "zeta" ]
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bats test/lib.bats`
Expected: FAIL — `pb_validate_theme: command not found`.

- [ ] **Step 3: Write minimal implementation**

`lib.sh`:
```bash
# lib.sh - shared helpers for prettyboot. Source this file; defines pb_* functions.

PB_BEGIN='# >>> prettyboot >>>'
PB_END='# <<< prettyboot <<<'

# Entries (relative to a theme dir) required for a theme to be valid.
PB_REQUIRED='theme.conf background.png selection_big.png selection_small.png icons'

# pb_validate_theme <themes_dir> <name>
# Prints what is missing to stderr. Returns 0 if valid, 1 otherwise.
pb_validate_theme() {
  local dir="$1/$2" missing="" item
  if [ ! -d "$dir" ]; then
    echo "theme '$2' not found" >&2
    return 1
  fi
  for item in $PB_REQUIRED; do
    [ -e "$dir/$item" ] || missing="$missing $item"
  done
  if [ -n "$missing" ]; then
    echo "theme '$2' missing:$missing" >&2
    return 1
  fi
  return 0
}

# pb_list_theme_names <themes_dir>  -> prints theme folder names, one per line, sorted
pb_list_theme_names() {
  [ -d "$1" ] || return 0
  local d
  for d in "$1"/*/; do
    [ -d "$d" ] || continue
    basename "$d"
  done | sort
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `bats test/lib.bats`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add lib.sh test/lib.bats
git commit -m "feat: add theme validation and discovery helpers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: lib.sh — refind.conf managed-block helpers

**Files:**
- Modify: `lib.sh`
- Test: `test/lib.bats` (append)

- [ ] **Step 1: Write the failing tests** (append to `test/lib.bats`)

```bash
@test "block_write then block_get returns include value" {
  conf="$TMP/refind.conf"; : > "$conf"
  pb_block_write "$conf" 10 themes/mac-dark/theme.conf
  run pb_block_get "$conf" include
  [ "$output" = "themes/mac-dark/theme.conf" ]
}

@test "block_get reads timeout value" {
  conf="$TMP/refind.conf"; : > "$conf"
  pb_block_write "$conf" 7 themes/mac-dark/theme.conf
  run pb_block_get "$conf" timeout
  [ "$output" = "7" ]
}

@test "block_write is idempotent (single block)" {
  conf="$TMP/refind.conf"; : > "$conf"
  pb_block_write "$conf" 10 themes/a/theme.conf
  pb_block_write "$conf" 5  themes/b/theme.conf
  run grep -c '>>> prettyboot >>>' "$conf"
  [ "$output" = "1" ]
  run pb_block_get "$conf" include
  [ "$output" = "themes/b/theme.conf" ]
}

@test "block_remove restores original content" {
  conf="$TMP/refind.conf"; printf 'timeout 20\nfoo bar\n' > "$conf"
  pb_block_write "$conf" 10 themes/a/theme.conf
  pb_block_remove "$conf"
  run cat "$conf"
  [ "$output" = "$(printf 'timeout 20\nfoo bar')" ]
}

@test "active_theme parses theme name from include" {
  conf="$TMP/refind.conf"; : > "$conf"
  pb_block_write "$conf" 10 themes/mac-light/theme.conf
  run pb_active_theme "$conf"
  [ "$output" = "mac-light" ]
}

@test "active_theme empty when no block" {
  conf="$TMP/refind.conf"; : > "$conf"
  run pb_active_theme "$conf"
  [ "$output" = "" ]
}

@test "block_write with empty include writes only timeout" {
  conf="$TMP/refind.conf"; : > "$conf"
  pb_block_write "$conf" 0 ""
  run pb_block_get "$conf" timeout
  [ "$output" = "0" ]
  run pb_block_get "$conf" include
  [ "$output" = "" ]
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bats test/lib.bats`
Expected: new tests FAIL — `pb_block_write: command not found`.

- [ ] **Step 3: Add implementation to `lib.sh`**

```bash
# pb_block_remove <conf>  -- delete the managed block in place (no-op if absent)
pb_block_remove() {
  local conf="$1"
  [ -f "$conf" ] || return 0
  awk -v b="$PB_BEGIN" -v e="$PB_END" '
    $0==b {skip=1; next}
    $0==e {skip=0; next}
    !skip {print}
  ' "$conf" > "$conf.tmp" && mv "$conf.tmp" "$conf"
}

# pb_block_get <conf> <key>  -- print value of key (timeout|include) inside the block
pb_block_get() {
  local conf="$1" key="$2"
  [ -f "$conf" ] || return 0
  awk -v b="$PB_BEGIN" -v e="$PB_END" -v k="$key" '
    $0==b {inb=1; next}
    $0==e {inb=0; next}
    inb && $1==k {print $2; exit}
  ' "$conf"
}

# pb_block_write <conf> <timeout> <include>  -- replace the block with these values
# include may be empty (writes timeout only). File is created if missing.
pb_block_write() {
  local conf="$1" timeout="$2" include="$3"
  [ -f "$conf" ] || : > "$conf"
  pb_block_remove "$conf"
  {
    echo "$PB_BEGIN"
    echo "timeout $timeout"
    [ -n "$include" ] && echo "include $include"
    echo "$PB_END"
  } >> "$conf"
}

# pb_active_theme <conf>  -- print active theme name parsed from the include line
pb_active_theme() {
  local inc
  inc="$(pb_block_get "$1" include)"
  case "$inc" in
    themes/*/theme.conf) inc="${inc#themes/}"; echo "${inc%/theme.conf}" ;;
  esac
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `bats test/lib.bats`
Expected: all lib tests PASS (11 total).

- [ ] **Step 5: Commit**

```bash
git add lib.sh test/lib.bats
git commit -m "feat: add refind.conf managed-block helpers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: lib.sh — deploy themes helper

**Files:**
- Modify: `lib.sh`
- Test: `test/lib.bats` (append)

- [ ] **Step 1: Write the failing test** (append to `test/lib.bats`)

```bash
@test "deploy_themes copies theme tree to destination" {
  make_theme "$TMP/src" mac-dark
  pb_deploy_themes "$TMP/src" "$TMP/dest"
  [ -f "$TMP/dest/mac-dark/theme.conf" ]
  [ -f "$TMP/dest/mac-dark/icons/os_linux.png" ]
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bats test/lib.bats`
Expected: FAIL — `pb_deploy_themes: command not found`.

- [ ] **Step 3: Add implementation to `lib.sh`**

```bash
# pb_deploy_themes <src_themes_dir> <dest_themes_dir>  -- copy all themes
pb_deploy_themes() {
  mkdir -p "$2"
  cp -r "$1"/. "$2"/
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bats test/lib.bats`
Expected: all 12 lib tests PASS.

- [ ] **Step 5: Commit**

```bash
git add lib.sh test/lib.bats
git commit -m "feat: add deploy_themes helper

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: prettyboot.sh — the CLI

**Files:**
- Create: `prettyboot.sh`
- Test: `test/cli.bats`

- [ ] **Step 1: Write the failing tests**

`test/cli.bats`:
```bash
load helper

PB() { REFIND_DIR="$TMP" "$BATS_TEST_DIRNAME/../prettyboot.sh" "$@"; }

setup() {
  TMP="$(mktemp -d)"
  : > "$TMP/refind.conf"
}
teardown() { rm -rf "$TMP"; }

@test "use activates a valid theme" {
  make_theme "$TMP/themes" mac-dark
  run PB use mac-dark
  [ "$status" -eq 0 ]
  run grep -c 'include themes/mac-dark/theme.conf' "$TMP/refind.conf"
  [ "$output" = "1" ]
}

@test "use refuses a broken theme and leaves conf untouched" {
  make_theme "$TMP/themes" mac-dark
  rm "$TMP/themes/mac-dark/background.png"
  run PB use mac-dark
  [ "$status" -ne 0 ]
  run grep -c 'include' "$TMP/refind.conf"
  [ "$output" = "0" ]
}

@test "list marks active theme and validity" {
  make_theme "$TMP/themes" mac-dark
  make_theme "$TMP/themes" broken
  rm "$TMP/themes/broken/theme.conf"
  PB use mac-dark
  run PB list
  [[ "$output" == *"* "*"mac-dark"* ]]
  [[ "$output" == *"broken"* ]]
}

@test "timeout sets value and preserves active include" {
  make_theme "$TMP/themes" mac-dark
  PB use mac-dark
  run PB timeout 25
  [ "$status" -eq 0 ]
  run grep -c '^timeout 25' "$TMP/refind.conf"
  [ "$output" = "1" ]
  run grep -c 'include themes/mac-dark/theme.conf' "$TMP/refind.conf"
  [ "$output" = "1" ]
}

@test "timeout off becomes 0" {
  make_theme "$TMP/themes" mac-dark
  PB use mac-dark
  PB timeout off
  run grep -c '^timeout 0' "$TMP/refind.conf"
  [ "$output" = "1" ]
}

@test "next cycles to the following valid theme" {
  make_theme "$TMP/themes" a
  make_theme "$TMP/themes" b
  PB use a
  run PB next
  [ "$status" -eq 0 ]
  run grep -c 'include themes/b/theme.conf' "$TMP/refind.conf"
  [ "$output" = "1" ]
}

@test "reset removes the managed block" {
  make_theme "$TMP/themes" mac-dark
  PB use mac-dark
  run PB reset
  [ "$status" -eq 0 ]
  run grep -c 'prettyboot' "$TMP/refind.conf"
  [ "$output" = "0" ]
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bats test/cli.bats`
Expected: FAIL — script not found / non-zero.

- [ ] **Step 3: Write `prettyboot.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/lib.sh"

REFIND_DIR="${REFIND_DIR:-/boot/efi/EFI/refind}"
CONF="$REFIND_DIR/refind.conf"
THEMES="$REFIND_DIR/themes"

usage() {
  cat <<EOF
prettyboot - rEFInd boot theme manager

Usage (run with sudo on a real system):
  prettyboot.sh list                 list themes (* active, ✓ valid, ✗ broken)
  prettyboot.sh use <theme>          activate a theme
  prettyboot.sh next                 switch to the next valid theme
  prettyboot.sh timeout <secs|off>   set boot menu timeout (off = wait forever)
  prettyboot.sh reset                remove prettyboot's settings (plain rEFInd)
EOF
}

cmd="${1:-}"
case "$cmd" in
  list)
    active="$(pb_active_theme "$CONF")"
    for name in $(pb_list_theme_names "$THEMES"); do
      if pb_validate_theme "$THEMES" "$name" 2>/dev/null; then mark="✓"; else mark="✗"; fi
      if [ "$name" = "$active" ]; then cur="*"; else cur=" "; fi
      printf "%s %s %s\n" "$cur" "$mark" "$name"
    done
    ;;
  use)
    name="${2:?usage: use <theme>}"
    pb_validate_theme "$THEMES" "$name" || exit 1
    t="$(pb_block_get "$CONF" timeout)"; t="${t:-10}"
    pb_block_write "$CONF" "$t" "themes/$name/theme.conf"
    echo "Active theme: $name"
    ;;
  next)
    active="$(pb_active_theme "$CONF")"
    valid=()
    for name in $(pb_list_theme_names "$THEMES"); do
      pb_validate_theme "$THEMES" "$name" 2>/dev/null && valid+=("$name")
    done
    [ "${#valid[@]}" -gt 0 ] || { echo "no valid themes found" >&2; exit 1; }
    idx=0
    for i in "${!valid[@]}"; do
      [ "${valid[$i]}" = "$active" ] && idx=$(( (i + 1) % ${#valid[@]} ))
    done
    exec "$0" use "${valid[$idx]}"
    ;;
  timeout)
    val="${2:?usage: timeout <secs|off>}"
    case "$val" in
      off) val=0 ;;
      ''|*[!0-9]*) echo "timeout must be a number or 'off'" >&2; exit 1 ;;
    esac
    inc="$(pb_block_get "$CONF" include)"
    pb_block_write "$CONF" "$val" "$inc"
    echo "Timeout: $val"
    ;;
  reset)
    pb_block_remove "$CONF"
    echo "prettyboot settings removed; plain rEFInd restored"
    ;;
  ''|-h|--help|help)
    usage
    ;;
  *)
    usage; exit 1
    ;;
esac
```

- [ ] **Step 4: Make executable and run tests**

Run: `chmod +x prettyboot.sh && bats test/cli.bats`
Expected: all 7 CLI tests PASS.

- [ ] **Step 5: Commit**

```bash
git add prettyboot.sh test/cli.bats
git commit -m "feat: add prettyboot CLI (list/use/next/timeout/reset)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: install.sh — install rEFInd + deploy themes

**Files:**
- Create: `install.sh`
- Test: `test/install.bats`

- [ ] **Step 1: Write the failing test**

`test/install.bats`:
```bash
load helper

setup() {
  TMP="$(mktemp -d)"
  export REFIND_DIR="$TMP/refind"
  mkdir -p "$REFIND_DIR"
  : > "$REFIND_DIR/refind.conf"
  export SRC_THEMES="$TMP/src"
  make_theme "$SRC_THEMES" mac-dark
}
teardown() { rm -rf "$TMP"; }

@test "install deploys themes, backs up conf, writes default block" {
  run "$BATS_TEST_DIRNAME/../install.sh"
  [ "$status" -eq 0 ]
  [ -f "$REFIND_DIR/themes/mac-dark/theme.conf" ]
  [ -f "$REFIND_DIR/refind.conf.prettyboot.bak" ]
  run grep -c 'include themes/mac-dark/theme.conf' "$REFIND_DIR/refind.conf"
  [ "$output" = "1" ]
  run grep -c '^timeout 10' "$REFIND_DIR/refind.conf"
  [ "$output" = "1" ]
}

@test "install backup is not overwritten on re-run" {
  "$BATS_TEST_DIRNAME/../install.sh"
  echo "EDITED" > "$REFIND_DIR/refind.conf.prettyboot.bak"
  "$BATS_TEST_DIRNAME/../install.sh"
  run cat "$REFIND_DIR/refind.conf.prettyboot.bak"
  [ "$output" = "EDITED" ]
}
```

Note: the test sets `REFIND_DIR` to an existing dir, so the rEFInd-install branch is skipped (only runs when the dir is absent).

- [ ] **Step 2: Run test to verify it fails**

Run: `bats test/install.bats`
Expected: FAIL — script not found.

- [ ] **Step 3: Write `install.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/lib.sh"

REFIND_DIR="${REFIND_DIR:-/boot/efi/EFI/refind}"
SRC_THEMES="${SRC_THEMES:-$here/themes}"

# 1. Ensure rEFInd is installed (only if its dir does not already exist).
if [ ! -d "$REFIND_DIR" ]; then
  if command -v apt-get >/dev/null 2>&1; then
    echo "Installing rEFInd via apt-get..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y refind
  else
    echo "rEFInd not found and apt-get unavailable. Install rEFInd manually, then re-run." >&2
    exit 1
  fi
fi

# 2. Verify rEFInd config exists.
[ -d "$REFIND_DIR" ] || { echo "rEFInd dir not found at $REFIND_DIR" >&2; exit 1; }
CONF="$REFIND_DIR/refind.conf"
[ -f "$CONF" ] || { echo "refind.conf not found at $CONF" >&2; exit 1; }

# 3. Back up the original config once.
[ -f "$CONF.prettyboot.bak" ] || cp "$CONF" "$CONF.prettyboot.bak"

# 4. Deploy bundled themes.
pb_deploy_themes "$SRC_THEMES" "$REFIND_DIR/themes"

# 5. Set defaults: 10s timeout, mac-dark active.
pb_block_write "$CONF" 10 themes/mac-dark/theme.conf

echo "prettyboot installed. Default theme: mac-dark, timeout 10s."
echo "Reboot to see it. Switch anytime:"
echo "  sudo $here/prettyboot.sh list"
echo "  sudo $here/prettyboot.sh use mac-light"
```

- [ ] **Step 4: Make executable and run test**

Run: `chmod +x install.sh && bats test/install.bats`
Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add install.sh test/install.bats
git commit -m "feat: add install.sh (rEFInd install + theme deploy)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: build-assets.sh — generate the Mac themes

**Files:**
- Create: `build-assets.sh`
- Test: `test/build.bats`

- [ ] **Step 1: Install build tools**

Run: `sudo apt-get install -y imagemagick librsvg2-bin`
Expected: `convert -version` and `rsvg-convert --version` both work.

- [ ] **Step 2: Write the failing test**

`test/build.bats`:
```bash
@test "build-assets produces valid mac-dark and mac-light themes" {
  command -v convert >/dev/null      || skip "imagemagick not installed"
  command -v rsvg-convert >/dev/null || skip "librsvg2-bin not installed"
  run "$BATS_TEST_DIRNAME/../build-assets.sh"
  [ "$status" -eq 0 ]
  for t in mac-dark mac-light; do
    for f in theme.conf background.png selection_big.png selection_small.png \
             icons/os_linux.png icons/os_win.png; do
      [ -f "$BATS_TEST_DIRNAME/../themes/$t/$f" ]
    done
    run identify -format '%m' "$BATS_TEST_DIRNAME/../themes/$t/background.png"
    [ "$output" = "PNG" ]
  done
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `bats test/build.bats`
Expected: FAIL — script not found (or `skip` if tools absent — then install tools first).

- [ ] **Step 4: Write `build-assets.sh`**

```bash
#!/usr/bin/env bash
# build-assets.sh - regenerate the mac-dark and mac-light theme PNGs.
# BUILD-TIME ONLY. End users never run this. Requires imagemagick + librsvg2-bin.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
W=1920; H=1080
md="$here/themes/mac-dark"
ml="$here/themes/mac-light"
mkdir -p "$md/icons" "$ml/icons"

# --- backgrounds ---
# mac-dark: Sonoma-style radial purple -> near-black
convert -size ${W}x${H} radial-gradient:'#3a2a5c'-'#08060f' "$md/background.png"
# mac-light: Big Sur-style color gradient + baked frosted panel (no live blur at boot)
convert -size ${W}x${H} gradient:'#ff9a8b'-'#8fd3f4' \
  -fill 'rgba(255,255,255,0.35)' -draw 'roundrectangle 560,400,1360,680,28,28' \
  "$ml/background.png"

# --- selection highlights ---
convert -size 160x160 xc:none -fill 'rgba(255,255,255,0.16)' \
  -draw 'roundrectangle 6,6,154,154,28,28' "$md/selection_big.png"
convert -size 64x64 xc:none -fill 'rgba(255,255,255,0.16)' \
  -draw 'roundrectangle 4,4,60,60,14,14' "$md/selection_small.png"
convert -size 160x160 xc:none -fill 'rgba(0,0,0,0.18)' \
  -draw 'roundrectangle 6,6,154,154,28,28' "$ml/selection_big.png"
convert -size 64x64 xc:none -fill 'rgba(0,0,0,0.18)' \
  -draw 'roundrectangle 4,4,60,60,14,14' "$ml/selection_small.png"

# --- icons (shared art for both themes) ---
tmp="$(mktemp -d)"
cat > "$tmp/os_linux.svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle cx="50" cy="50" r="46" fill="#E95420"/>
  <g fill="#fff">
    <circle cx="50" cy="22" r="8"/><circle cx="26" cy="64" r="8"/><circle cx="74" cy="64" r="8"/>
  </g>
  <g stroke="#fff" stroke-width="6" fill="none">
    <path d="M50 30 A20 20 0 0 1 67 58"/>
    <path d="M33 58 A20 20 0 0 1 50 30"/>
    <path d="M67 58 A20 20 0 0 1 33 58"/>
  </g>
</svg>
SVG
cat > "$tmp/os_win.svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <g fill="#3a9bdc">
    <rect x="14" y="14" width="33" height="33" rx="2"/>
    <rect x="53" y="14" width="33" height="33" rx="2"/>
    <rect x="14" y="53" width="33" height="33" rx="2"/>
    <rect x="53" y="53" width="33" height="33" rx="2"/>
  </g>
</svg>
SVG
for d in "$md" "$ml"; do
  rsvg-convert -w 128 -h 128 "$tmp/os_linux.svg" -o "$d/icons/os_linux.png"
  rsvg-convert -w 128 -h 128 "$tmp/os_win.svg"   -o "$d/icons/os_win.png"
done
rm -rf "$tmp"

# --- theme.conf for each theme ---
write_conf() {  # <dir> <name>
  cat > "$1/theme.conf" <<EOF
# prettyboot theme: $2
banner themes/$2/background.png
banner_scale fillscreen
icons_dir themes/$2/icons
selection_big themes/$2/selection_big.png
selection_small themes/$2/selection_small.png
big_icon_size 128
small_icon_size 48
EOF
}
write_conf "$md" mac-dark
write_conf "$ml" mac-light

echo "Generated themes: mac-dark, mac-light"
```

- [ ] **Step 5: Make executable, run it, and run the test**

Run: `chmod +x build-assets.sh && ./build-assets.sh && bats test/build.bats`
Expected: script prints "Generated themes…"; test PASSES.

- [ ] **Step 6: Verify the generated theme passes prettyboot validation**

Run: `REFIND_DIR="$PWD" ./prettyboot.sh list` (with `themes/` in the repo root)
Expected: `mac-dark` and `mac-light` both show `✓`.
(If it errors because `themes` is at repo root not `$PWD/themes`: run `cp -r themes /tmp/r/ ; REFIND_DIR=/tmp/r ./prettyboot.sh list` — both ✓.)

- [ ] **Step 7: Commit (script + vendored assets)**

```bash
git add build-assets.sh test/build.bats themes/
git commit -m "feat: generate and vendor mac-dark/mac-light themes

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: README.md

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

````markdown
# prettyboot

A graphical, themeable boot picker for UEFI dual-boot PCs (e.g. Ubuntu + Windows),
built on [rEFInd](https://www.rodsbooks.com/refind/). Ships a Mac-style theme in
light and dark, and lets you switch or add themes with one command — safely.

> **Scope:** UEFI firmware + rEFInd. Themes follow rEFInd's standard layout, so any
> rEFInd theme from the internet drops in and works.

## Install

```bash
git clone https://github.com/SivaKanth007/prettyboot
cd prettyboot
sudo ./install.sh
```

This installs rEFInd (via apt), deploys the bundled themes, backs up your existing
`refind.conf`, sets the boot-menu timeout to 10 seconds, and activates `mac-dark`.
Reboot to see it.

## Usage

```bash
sudo ./prettyboot.sh list                # list themes (* active, ✓ valid, ✗ broken)
sudo ./prettyboot.sh use mac-light       # activate a theme
sudo ./prettyboot.sh use mac-dark
sudo ./prettyboot.sh next                # cycle to the next valid theme
sudo ./prettyboot.sh timeout 0           # menu waits forever (0 = no auto-boot)
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
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README (usage, theme contract, dev)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: Full test run + publish to GitHub

**Files:** none (publish step)

- [ ] **Step 1: Run the whole test suite**

Run: `bats test/`
Expected: all tests PASS (lib 12, cli 7, install 2, build 1 — build may `skip` if image tools absent).

- [ ] **Step 2: Confirm clean working tree**

Run: `git status`
Expected: nothing to commit, working tree clean.

- [ ] **Step 3: Create the public GitHub repo and push**

Run:
```bash
gh repo create prettyboot --public --source=. --remote=origin \
  --description "Graphical, themeable rEFInd boot picker for UEFI dual-boot (Mac-style light/dark)" \
  --push
```
Expected: repo created at `https://github.com/SivaKanth007/prettyboot`, `main` pushed.

- [ ] **Step 4: Verify remote**

Run: `gh repo view --web` (or `git remote -v && git log --oneline origin/main`)
Expected: repo visible on GitHub with all files.

---

## Notes for the executor

- **Reboot verification is manual.** No test can confirm the actual boot screen.
  After install on a real machine, reboot and confirm the menu appears with the
  themed look. If anything looks wrong, `sudo ./prettyboot.sh reset` reverts to
  plain rEFInd; the backup `refind.conf.prettyboot.bak` is the full fallback.
- **Do not run `install.sh` or `build-assets.sh` against the real `/boot/efi`
  during development.** Use `REFIND_DIR`/`SRC_THEMES` overrides and temp dirs, as
  the tests do. Real install happens only when the user chooses to run it.
- **Font handling:** v1 ships no `font.png`; rEFInd's built-in font is used. If the
  user later wants custom fonts, add `font.png` per theme and update `theme.conf`.
- **`use` exits non-zero on a broken theme** and leaves `refind.conf` untouched —
  this is the core safety guarantee; keep it intact.
```
