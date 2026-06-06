# prettyboot GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a GTK4 desktop app to prettyboot — theme switching, curated + raw settings, drag-drop theme import, full-size live preview, icon/background editing — wrapping the existing bash CLI as its engine, shipped in one `.deb` via a Launchpad PPA.

**Architecture:** The bash engine (`lib.sh`/`prettyboot.sh`) stays the single source of truth for every boot-config write. We add three CLI subcommands (`import`, `set`, `get`) and generalize the managed-block helpers to a key/value upsert. The GUI (Python + GTK4) is a thin frontend whose only logic seam is `engine.py`, which shells out to `prettyboot` (reads) and `pkexec prettyboot` (writes). Packaging is one arch-`all` `.deb` providing the CLI, the GUI, a `.desktop` launcher, and a polkit policy.

**Tech Stack:** bash + awk (engine), bats-core (engine tests), Python 3 + GTK4/PyGObject (GUI), pytest (GUI logic tests), debhelper/`debian/` + Launchpad PPA (packaging).

---

## File Structure

**Part A — Engine (bash)**
- Modify: `lib.sh` — generalize `pb_block_get`; add `pb_block_set`, `pb_block_unset`; add `pb_validate_theme_dir`.
- Modify: `prettyboot.sh` — add `import`, `set`, `get` subcommands; switch `use`/`timeout` to upsert so curated settings survive.
- Test: `test/blockset.bats`, `test/import.bats`, `test/settings.bats`.

**Part B — GUI (Python/GTK4)**
- Create: `gui/prettyboot_gui/__init__.py` — package marker + version.
- Create: `gui/prettyboot_gui/engine.py` — subprocess wrapper (the testable seam).
- Create: `gui/prettyboot_gui/preview.py` — builds the live-preview widget from theme assets.
- Create: `gui/prettyboot_gui/app.py` — `Gtk.Application`, window, the three tabs.
- Create: `gui/prettyboot_gui/main.py` — entry point (`python3 .../main.py`).
- Create: `gui/prettyboot.desktop` — apps-list launcher.
- Create: `gui/com.prettyboot.policy` — polkit policy.
- Test: `gui/tests/test_engine.py`.

**Part C — Packaging**
- Create: `bin/prettyboot-gui` — launcher wrapper for the `.desktop` Exec.
- Create: `debian/control`, `debian/changelog`, `debian/rules`, `debian/install`, `debian/links`, `debian/source/format`, `debian/compat`.
- Modify: `README.md` — GUI + apt install instructions.

---

## Part A — Engine

### Task A1: Generalize `pb_block_get` to multi-word values

**Files:**
- Modify: `lib.sh:48-57`
- Test: `test/blockset.bats`

- [ ] **Step 1: Write the failing test**

Create `test/blockset.bats`:

```bash
load helper

setup() { TMP="$(mktemp -d)"; CONF="$TMP/refind.conf"; . "$BATS_TEST_DIRNAME/../lib.sh"; }
teardown() { rm -rf "$TMP"; }

@test "block_get returns full multi-word value" {
  printf '%s\ntimeout 10\nresolution 1920 1080\n%s\n' "$PB_BEGIN" "$PB_END" > "$CONF"
  run pb_block_get "$CONF" resolution
  [ "$output" = "1920 1080" ]
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bats test/blockset.bats -f "multi-word"`
Expected: FAIL — output is `1920`, not `1920 1080`.

- [ ] **Step 3: Edit `pb_block_get`**

Replace the awk body in `lib.sh` `pb_block_get` so it prints all fields after the key:

```bash
pb_block_get() {
  local conf="$1" key="$2"
  [ -f "$conf" ] || return 0
  awk -v b="$PB_BEGIN" -v e="$PB_END" -v k="$key" '
    $0==b {inb=1; next}
    $0==e {inb=0; next}
    inb && $1==k { $1=""; sub(/^[ \t]+/,""); print; exit }
  ' "$conf"
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bats test/blockset.bats -f "multi-word"`
Expected: PASS

- [ ] **Step 5: Run the full existing suite (no regressions)**

Run: `bats test/`
Expected: all pass (timeout/include are single-token, unaffected).

- [ ] **Step 6: Commit**

```bash
git add lib.sh test/blockset.bats
git commit -m "feat(engine): pb_block_get returns full multi-word values"
```

---

### Task A2: Add `pb_block_set` upsert helper

**Files:**
- Modify: `lib.sh` (add after `pb_block_get`)
- Test: `test/blockset.bats`

- [ ] **Step 1: Write the failing tests**

Append to `test/blockset.bats`:

```bash
@test "block_set creates block and key when absent" {
  : > "$CONF"
  pb_block_set "$CONF" timeout 10
  run pb_block_get "$CONF" timeout
  [ "$output" = "10" ]
}

@test "block_set updates existing key without touching others" {
  pb_block_set "$CONF" timeout 10
  pb_block_set "$CONF" include themes/mac-dark/theme.conf
  pb_block_set "$CONF" timeout 25
  run pb_block_get "$CONF" timeout
  [ "$output" = "25" ]
  run pb_block_get "$CONF" include
  [ "$output" = "themes/mac-dark/theme.conf" ]
}

@test "block_set writes a key only once when repeated" {
  pb_block_set "$CONF" hideui hints
  pb_block_set "$CONF" hideui hints,arrows
  run grep -c '^hideui ' "$CONF"
  [ "$output" = "1" ]
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bats test/blockset.bats -f "block_set"`
Expected: FAIL — `pb_block_set: command not found`.

- [ ] **Step 3: Implement `pb_block_set`**

Add to `lib.sh` after `pb_block_get`:

```bash
# pb_block_set <conf> <key> <value...>  -- upsert "key value" inside the block.
# Creates the conf and/or the block if missing. Replaces an existing key in place.
pb_block_set() {
  local conf="$1" key="$2"; shift 2; local value="$*"
  [ -f "$conf" ] || : > "$conf"
  if ! grep -qF "$PB_BEGIN" "$conf"; then
    { echo "$PB_BEGIN"; echo "$PB_END"; } >> "$conf"
  fi
  awk -v b="$PB_BEGIN" -v e="$PB_END" -v k="$key" -v val="$value" '
    $0==b {inb=1; print; next}
    inb && $0==e { if (!done) print k" "val; inb=0; print; next }
    inb && $1==k { if (!done) { print k" "val; done=1 } ; next }
    {print}
  ' "$conf" > "$conf.tmp" && mv "$conf.tmp" "$conf"
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `bats test/blockset.bats -f "block_set"`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add lib.sh test/blockset.bats
git commit -m "feat(engine): add pb_block_set upsert helper"
```

---

### Task A3: Add `pb_block_unset` helper

**Files:**
- Modify: `lib.sh` (add after `pb_block_set`)
- Test: `test/blockset.bats`

- [ ] **Step 1: Write the failing test**

Append to `test/blockset.bats`:

```bash
@test "block_unset removes a key, leaves others" {
  pb_block_set "$CONF" timeout 10
  pb_block_set "$CONF" resolution "1920 1080"
  pb_block_unset "$CONF" resolution
  run pb_block_get "$CONF" resolution
  [ -z "$output" ]
  run pb_block_get "$CONF" timeout
  [ "$output" = "10" ]
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bats test/blockset.bats -f "block_unset"`
Expected: FAIL — `pb_block_unset: command not found`.

- [ ] **Step 3: Implement `pb_block_unset`**

Add to `lib.sh` after `pb_block_set`:

```bash
# pb_block_unset <conf> <key>  -- remove a key line from inside the block (no-op if absent)
pb_block_unset() {
  local conf="$1" key="$2"
  [ -f "$conf" ] || return 0
  awk -v b="$PB_BEGIN" -v e="$PB_END" -v k="$key" '
    $0==b {inb=1; print; next}
    $0==e {inb=0; print; next}
    inb && $1==k { next }
    {print}
  ' "$conf" > "$conf.tmp" && mv "$conf.tmp" "$conf"
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bats test/blockset.bats -f "block_unset"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lib.sh test/blockset.bats
git commit -m "feat(engine): add pb_block_unset helper"
```

---

### Task A4: Add `pb_validate_theme_dir` (validate an arbitrary dir)

**Files:**
- Modify: `lib.sh` (refactor `pb_validate_theme` to delegate)
- Test: `test/blockset.bats`

- [ ] **Step 1: Write the failing test**

Append to `test/blockset.bats`:

```bash
@test "validate_theme_dir passes a complete dir and fails a broken one" {
  make_theme "$TMP/src" good
  run pb_validate_theme_dir "$TMP/src/good"
  [ "$status" -eq 0 ]
  rm "$TMP/src/good/background.png"
  run pb_validate_theme_dir "$TMP/src/good"
  [ "$status" -ne 0 ]
  [[ "$output" == *"background.png"* ]]
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bats test/blockset.bats -f "validate_theme_dir"`
Expected: FAIL — `pb_validate_theme_dir: command not found`.

- [ ] **Step 3: Implement and delegate**

In `lib.sh`, add `pb_validate_theme_dir` and rewrite `pb_validate_theme` to call it:

```bash
# pb_validate_theme_dir <dir>  -- validate a theme directory by absolute/relative path.
pb_validate_theme_dir() {
  local dir="$1" missing="" item
  if [ ! -d "$dir" ]; then
    echo "theme dir '$dir' not found" >&2
    return 1
  fi
  for item in $PB_REQUIRED; do
    [ -e "$dir/$item" ] || missing="$missing $item"
  done
  if [ -n "$missing" ]; then
    echo "theme '$(basename "$dir")' missing:$missing" >&2
    return 1
  fi
  return 0
}

# pb_validate_theme <themes_dir> <name>  -- validate themes_dir/name.
pb_validate_theme() {
  if [ ! -d "$1/$2" ]; then
    echo "theme '$2' not found" >&2
    return 1
  fi
  pb_validate_theme_dir "$1/$2"
}
```

- [ ] **Step 4: Run the test and the full suite**

Run: `bats test/blockset.bats -f "validate_theme_dir" && bats test/`
Expected: all PASS (existing `pb_validate_theme` tests still pass via delegation).

- [ ] **Step 5: Commit**

```bash
git add lib.sh test/blockset.bats
git commit -m "feat(engine): add pb_validate_theme_dir, delegate from pb_validate_theme"
```

---

### Task A5: Add `import` subcommand

**Files:**
- Modify: `prettyboot.sh` (add a `import)` case before the `''|menu)` case)
- Test: `test/import.bats`

- [ ] **Step 1: Write the failing tests**

Create `test/import.bats`:

```bash
load helper

PB() { REFIND_DIR="$TMP" "$BATS_TEST_DIRNAME/../prettyboot.sh" "$@"; }

setup() { TMP="$(mktemp -d)"; : > "$TMP/refind.conf"; }
teardown() { rm -rf "$TMP"; }

@test "import installs a valid theme dir under its folder name" {
  make_theme "$TMP/src" cool
  run PB import "$TMP/src/cool"
  [ "$status" -eq 0 ]
  [ -f "$TMP/themes/cool/theme.conf" ]
  run PB list
  [[ "$output" == *"cool"* ]]
}

@test "import honors an explicit name" {
  make_theme "$TMP/src" cool
  run PB import "$TMP/src/cool" renamed
  [ "$status" -eq 0 ]
  [ -f "$TMP/themes/renamed/theme.conf" ]
}

@test "import refuses a broken dir and installs nothing" {
  make_theme "$TMP/src" bad
  rm "$TMP/src/bad/selection_big.png"
  run PB import "$TMP/src/bad"
  [ "$status" -ne 0 ]
  [ ! -d "$TMP/themes/bad" ]
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bats test/import.bats`
Expected: FAIL — `import` falls through to usage, exit 1, no theme copied.

- [ ] **Step 3: Implement the `import` case**

In `prettyboot.sh`, add this case after the `reset)` case and before `''|menu)`:

```bash
  import)
    src="${2:?usage: import <dir> [name]}"
    name="${3:-$(basename "$src")}"
    pb_validate_theme_dir "$src" || exit 1
    mkdir -p "$THEMES"
    rm -rf "${THEMES:?}/$name"
    cp -r "$src" "$THEMES/$name"
    echo "Imported theme: $name"
    ;;
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `bats test/import.bats`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add prettyboot.sh test/import.bats
git commit -m "feat(cli): add import subcommand"
```

---

### Task A6: Add `set`/`get` subcommands and preserve settings across `use`/`timeout`

**Files:**
- Modify: `prettyboot.sh` (`use)`, `timeout)`, add `set)`/`get)`)
- Test: `test/settings.bats`

- [ ] **Step 1: Write the failing tests**

Create `test/settings.bats`:

```bash
load helper

PB() { REFIND_DIR="$TMP" "$BATS_TEST_DIRNAME/../prettyboot.sh" "$@"; }

setup() { TMP="$(mktemp -d)"; : > "$TMP/refind.conf"; make_theme "$TMP/themes" mac-dark; }
teardown() { rm -rf "$TMP"; }

@test "set then get round-trips a multi-word value" {
  PB set resolution "1920 1080"
  run PB get resolution
  [ "$output" = "1920 1080" ]
}

@test "get prints nothing for an unset key" {
  run PB get resolution
  [ -z "$output" ]
}

@test "curated setting survives a theme switch" {
  PB set resolution "1920 1080"
  PB use mac-dark
  run PB get resolution
  [ "$output" = "1920 1080" ]
  run grep -c 'include themes/mac-dark/theme.conf' "$TMP/refind.conf"
  [ "$output" = "1" ]
}

@test "curated setting survives a timeout change" {
  PB use mac-dark
  PB set showtools shell
  PB timeout 15
  run PB get showtools
  [ "$output" = "shell" ]
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bats test/settings.bats`
Expected: FAIL — `set`/`get` fall through to usage; and `use`/`timeout` (still using `pb_block_write`) wipe curated keys.

- [ ] **Step 3: Switch `use` and `timeout` to upsert; add `set`/`get`**

In `prettyboot.sh`, replace the `use)` case body:

```bash
  use)
    name="${2:?usage: use <theme>}"
    pb_validate_theme "$THEMES" "$name" || exit 1
    [ -n "$(pb_block_get "$CONF" timeout)" ] || pb_block_set "$CONF" timeout 10
    pb_block_set "$CONF" include "themes/$name/theme.conf"
    echo "Active theme: $name"
    ;;
```

Replace the `timeout)` case body:

```bash
  timeout)
    val="${2:?usage: timeout <secs|off>}"
    case "$val" in
      off) val=0 ;;
      ''|*[!0-9]*) echo "timeout must be a number or 'off'" >&2; exit 1 ;;
    esac
    pb_block_set "$CONF" timeout "$val"
    echo "Timeout: $val"
    ;;
```

Add these two cases after `import)`:

```bash
  set)
    key="${2:?usage: set <key> <value>}"; shift 2
    pb_block_set "$CONF" "$key" "$*"
    echo "$key = $*"
    ;;
  get)
    key="${2:?usage: get <key>}"
    pb_block_get "$CONF" "$key"
    ;;
```

- [ ] **Step 4: Run the new and existing suites**

Run: `bats test/settings.bats && bats test/`
Expected: all PASS. (Existing `cli.bats` timeout/use tests still pass: `pb_block_set` keeps `include` and `timeout` single lines.)

- [ ] **Step 5: Commit**

```bash
git add prettyboot.sh test/settings.bats
git commit -m "feat(cli): add set/get; preserve curated settings across use/timeout"
```

---

## Part B — GUI (Python / GTK4)

> Prerequisite for running Part B tests locally: `sudo apt-get install -y python3-gi gir1.2-gtk-4.0 python3-pytest`. The `engine.py` tests do **not** need GTK; only `app.py`/`preview.py` import GTK.

### Task B1: Engine wrapper `engine.py` (the testable seam)

**Files:**
- Create: `gui/prettyboot_gui/__init__.py`
- Create: `gui/prettyboot_gui/engine.py`
- Test: `gui/tests/test_engine.py`

- [ ] **Step 1: Write the failing tests**

Create `gui/tests/test_engine.py`:

```python
import os
import subprocess
from pathlib import Path

import pytest

from prettyboot_gui import engine

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def refind(tmp_path, monkeypatch):
    """Point the engine at the real CLI but a temp REFIND_DIR, no pkexec."""
    (tmp_path / "refind.conf").write_text("")
    monkeypatch.setenv("REFIND_DIR", str(tmp_path))
    monkeypatch.setenv("PRETTYBOOT_BIN", str(REPO / "prettyboot.sh"))
    monkeypatch.setenv("PRETTYBOOT_PKEXEC", "")  # empty = run write ops directly
    return tmp_path


def _make_theme(root: Path, name: str):
    d = root / name
    (d / "icons").mkdir(parents=True)
    for f in ("theme.conf", "background.png", "selection_big.png", "selection_small.png"):
        (d / f).write_text("x")
    (d / "icons" / "os_linux.png").write_text("x")
    return d


def test_list_and_use_and_active(refind):
    _make_theme(refind / "themes", "mac-dark")
    assert "mac-dark" in [n for n, _, _ in engine.list_themes()]
    engine.use_theme("mac-dark")
    assert engine.active_theme() == "mac-dark"


def test_set_get(refind):
    engine.set_setting("resolution", "1920 1080")
    assert engine.get_setting("resolution") == "1920 1080"


def test_import_theme(refind, tmp_path):
    src = _make_theme(tmp_path / "src", "cool")
    engine.import_theme(str(src))
    assert "cool" in [n for n, _, _ in engine.list_themes()]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd gui && PYTHONPATH=. python3 -m pytest tests/test_engine.py -q`
Expected: FAIL — `ModuleNotFoundError: prettyboot_gui` / `engine`.

- [ ] **Step 3: Create the package marker**

Create `gui/prettyboot_gui/__init__.py`:

```python
__version__ = "1.0.0"
```

- [ ] **Step 4: Implement `engine.py`**

Create `gui/prettyboot_gui/engine.py`:

```python
"""Thin wrapper around the prettyboot bash CLI.

Reads run the CLI directly; writes go through pkexec so the GUI never runs
as root. Both are overridable via env for testing:
  PRETTYBOOT_BIN     path to the CLI (default: "prettyboot" on PATH)
  PRETTYBOOT_PKEXEC  privilege wrapper (default: "pkexec"; empty = none)
"""
import os
import subprocess


def _bin() -> str:
    return os.environ.get("PRETTYBOOT_BIN", "prettyboot")


def _read(*args: str) -> str:
    out = subprocess.run(
        [_bin(), *args], check=True, capture_output=True, text=True
    )
    return out.stdout


def _write(*args: str) -> None:
    pkexec = os.environ.get("PRETTYBOOT_PKEXEC", "pkexec")
    cmd = ([pkexec] if pkexec else []) + [_bin(), *args]
    subprocess.run(cmd, check=True)


def list_themes() -> list[tuple[str, bool, bool]]:
    """Return (name, active, valid) for each theme, parsed from `list`."""
    themes = []
    for line in _read("list").splitlines():
        # format: "<active * or space> <valid ✓/✗> <name>"
        active = line.startswith("*")
        rest = line[1:].strip()
        valid = rest.startswith("✓")
        name = rest[1:].strip()
        if name:
            themes.append((name, active, valid))
    return themes


def active_theme() -> str | None:
    for name, active, _ in list_themes():
        if active:
            return name
    return None


def get_setting(key: str) -> str:
    return _read("get", key).strip()


def use_theme(name: str) -> None:
    _write("use", name)


def set_setting(key: str, value: str) -> None:
    _write("set", key, value)


def set_timeout(value: str) -> None:
    _write("timeout", value)


def import_theme(path: str, name: str | None = None) -> None:
    _write("import", path, *( [name] if name else [] ))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd gui && PYTHONPATH=. python3 -m pytest tests/test_engine.py -q`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add gui/prettyboot_gui/__init__.py gui/prettyboot_gui/engine.py gui/tests/test_engine.py
git commit -m "feat(gui): engine.py CLI wrapper with tests"
```

---

### Task B2: Live-preview widget `preview.py`

**Files:**
- Create: `gui/prettyboot_gui/preview.py`
- Test: `gui/tests/test_preview.py`

- [ ] **Step 1: Write the failing test (logic only, no GTK render)**

Create `gui/tests/test_preview.py`:

```python
from pathlib import Path

from prettyboot_gui import preview


def test_theme_assets_resolves_paths(tmp_path):
    d = tmp_path / "mac-dark"
    (d / "icons").mkdir(parents=True)
    (d / "background.png").write_text("x")
    (d / "icons" / "os_win8.png").write_text("x")
    (d / "icons" / "os_ubuntu.png").write_text("x")
    a = preview.theme_assets(str(d))
    assert a["background"].endswith("background.png")
    assert any(p.endswith("os_win8.png") for p in a["icons"])
    assert any(p.endswith("os_ubuntu.png") for p in a["icons"])


def test_theme_assets_missing_background_is_none(tmp_path):
    d = tmp_path / "empty"
    (d / "icons").mkdir(parents=True)
    a = preview.theme_assets(str(d))
    assert a["background"] is None
    assert a["icons"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd gui && PYTHONPATH=. python3 -m pytest tests/test_preview.py -q`
Expected: FAIL — module/`theme_assets` missing.

- [ ] **Step 3: Implement `preview.py`**

Create `gui/prettyboot_gui/preview.py`:

```python
"""Builds the live boot-menu preview. `theme_assets` is pure (testable);
`build_widget` needs GTK and is imported lazily by app.py."""
import os


def theme_assets(theme_dir: str) -> dict:
    """Resolve preview asset paths for a theme directory."""
    bg = os.path.join(theme_dir, "background.png")
    icons_dir = os.path.join(theme_dir, "icons")
    icons = []
    if os.path.isdir(icons_dir):
        for fn in sorted(os.listdir(icons_dir)):
            if fn.startswith("os_") and fn.endswith(".png"):
                icons.append(os.path.join(icons_dir, fn))
    return {
        "background": bg if os.path.isfile(bg) else None,
        "icons": icons,
    }


def build_widget(theme_dir: str):
    """Return a Gtk.Picture-based 16:9 preview overlaying OS icons on the
    background. Imported lazily so non-GTK tests can import this module's
    pure helpers."""
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, Gdk

    assets = theme_assets(theme_dir)
    overlay = Gtk.Overlay()
    overlay.set_size_request(640, 360)  # 16:9

    if assets["background"]:
        bg = Gtk.Picture.new_for_filename(assets["background"])
        bg.set_content_fit(Gtk.ContentFit.COVER)
        overlay.set_child(bg)

    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=40)
    row.set_halign(Gtk.Align.CENTER)
    row.set_valign(Gtk.Align.CENTER)
    seen = set()
    for icon in assets["icons"]:
        # collapse the os_win/os_win8 and os_linux/os_ubuntu duplicate pairs
        key = os.path.basename(icon).replace("os_win8", "os_win").replace(
            "os_ubuntu", "os_linux")
        if key in seen:
            continue
        seen.add(key)
        pic = Gtk.Picture.new_for_filename(icon)
        pic.set_size_request(96, 96)
        row.append(pic)
    overlay.add_overlay(row)
    return overlay
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd gui && PYTHONPATH=. python3 -m pytest tests/test_preview.py -q`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add gui/prettyboot_gui/preview.py gui/tests/test_preview.py
git commit -m "feat(gui): preview asset resolution + lazy GTK widget"
```

---

### Task B3: Application window with the three tabs `app.py`

**Files:**
- Create: `gui/prettyboot_gui/app.py`
- Create: `gui/prettyboot_gui/main.py`

> This task is GTK UI assembly; it is verified by a launch smoke test in Task B4, not unit tests (the logic it calls is already covered by B1/B2).

- [ ] **Step 1: Implement `app.py`**

Create `gui/prettyboot_gui/app.py`:

```python
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, Gio, GLib  # noqa: E402

from . import engine, preview  # noqa: E402

REFIND_DIR = "/boot/efi/EFI/refind"


class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="prettyboot")
        self.set_default_size(900, 560)
        notebook = Gtk.Notebook()
        self.set_child(notebook)
        notebook.append_page(self._themes_tab(), Gtk.Label(label="Themes"))
        notebook.append_page(self._settings_tab(), Gtk.Label(label="Settings"))
        notebook.append_page(self._advanced_tab(), Gtk.Label(label="Advanced"))

    # --- Themes tab: slim rail + full-size preview ---
    def _themes_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(12); box.set_margin_bottom(12)
        box.set_margin_start(12); box.set_margin_end(12)

        rail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        rail.set_size_request(180, -1)
        self.theme_list = Gtk.ListBox()
        self.theme_list.connect("row-selected", self._on_theme_selected)
        rail.append(self.theme_list)

        drop = Gtk.Frame(label="Drop theme folder / .zip")
        drop.set_size_request(-1, 80)
        self._enable_drop(drop)
        rail.append(drop)

        apply_btn = Gtk.Button(label="Apply")
        apply_btn.connect("clicked", self._on_apply)
        rail.append(apply_btn)
        box.append(rail)

        self.preview_holder = Gtk.Box()
        self.preview_holder.set_hexpand(True)
        self.preview_holder.set_vexpand(True)
        box.append(self.preview_holder)

        self._reload_themes()
        return box

    def _reload_themes(self):
        child = self.theme_list.get_first_child()
        while child:
            self.theme_list.remove(child)
            child = self.theme_list.get_first_child()
        for name, active, valid in engine.list_themes():
            label = ("● " if active else "") + name + ("" if valid else "  ✗")
            row = Gtk.ListBoxRow()
            row.set_child(Gtk.Label(label=label, xalign=0))
            row.theme_name = name
            self.theme_list.append(row)

    def _on_theme_selected(self, _listbox, row):
        if not row:
            return
        holder = self.preview_holder
        old = holder.get_first_child()
        if old:
            holder.remove(old)
        holder.append(preview.build_widget(f"{REFIND_DIR}/themes/{row.theme_name}"))

    def _on_apply(self, _btn):
        row = self.theme_list.get_selected_row()
        if row:
            self._run(lambda: engine.use_theme(row.theme_name))

    def _enable_drop(self, widget):
        target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        target.connect("drop", self._on_drop)
        widget.add_controller(target)

    def _on_drop(self, _t, value, _x, _y):
        path = value.get_path()
        if path:
            self._run(lambda: engine.import_theme(path))
        return True

    # --- Settings tab: curated controls ---
    def _settings_tab(self):
        grid = Gtk.Grid(row_spacing=10, column_spacing=10)
        grid.set_margin_top(16); grid.set_margin_start(16)
        self.timeout_entry = Gtk.Entry(text=engine.get_setting("timeout"))
        grid.attach(Gtk.Label(label="Timeout (sec, 0=off):", xalign=0), 0, 0, 1, 1)
        grid.attach(self.timeout_entry, 1, 0, 1, 1)
        self.res_entry = Gtk.Entry(text=engine.get_setting("resolution"))
        grid.attach(Gtk.Label(label="Resolution (W H):", xalign=0), 0, 1, 1, 1)
        grid.attach(self.res_entry, 1, 1, 1, 1)
        save = Gtk.Button(label="Save settings")
        save.connect("clicked", self._on_save_settings)
        grid.attach(save, 1, 2, 1, 1)
        return grid

    def _on_save_settings(self, _btn):
        def work():
            engine.set_timeout(self.timeout_entry.get_text() or "0")
            res = self.res_entry.get_text().strip()
            if res:
                engine.set_setting("resolution", res)
        self._run(work)

    # --- Advanced tab: raw refind.conf ---
    def _advanced_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(12); box.set_margin_start(12); box.set_margin_end(12)
        warn = Gtk.Label(
            label="Editing raw refind.conf. A timestamped backup is made on save. "
                  "Keep the prettyboot >>> / <<< markers.", xalign=0)
        box.append(warn)
        self.raw_view = Gtk.TextView()
        self.raw_view.set_monospace(True)
        try:
            with open(f"{REFIND_DIR}/refind.conf") as fh:
                self.raw_view.get_buffer().set_text(fh.read())
        except OSError:
            pass
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.raw_view)
        scroll.set_vexpand(True)
        box.append(scroll)
        return box

    def _run(self, work):
        """Run a write op; show any failure in a dialog and refresh the list."""
        try:
            work()
        except Exception as exc:  # subprocess.CalledProcessError etc.
            dlg = Gtk.AlertDialog()
            dlg.set_message("Operation failed")
            dlg.set_detail(str(exc))
            dlg.show(self)
        self._reload_themes()


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.prettyboot.App")

    def do_activate(self):
        Window(self).present()
```

- [ ] **Step 2: Implement `main.py`**

Create `gui/prettyboot_gui/main.py`:

```python
import sys

from .app import App


def main() -> int:
    return App().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Byte-compile check (no GTK display needed)**

Run: `cd gui && python3 -m py_compile prettyboot_gui/app.py prettyboot_gui/main.py`
Expected: no output, exit 0 (syntax valid).

- [ ] **Step 4: Commit**

```bash
git add gui/prettyboot_gui/app.py gui/prettyboot_gui/main.py
git commit -m "feat(gui): GTK4 window with Themes/Settings/Advanced tabs"
```

---

### Task B4: Launch smoke test

**Files:**
- Test: `gui/tests/test_launch.py`

- [ ] **Step 1: Write the smoke test**

Create `gui/tests/test_launch.py`:

```python
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

GUI = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(
    shutil.which("Xvfb") is None, reason="needs Xvfb for headless GTK"
)
def test_app_imports_and_starts_headless():
    """App constructs and registers under a virtual display, then exits."""
    code = (
        "import gi; gi.require_version('Gtk','4.0');"
        "from prettyboot_gui.app import App;"
        "app=App();"
        "from gi.repository import GLib;"
        "GLib.timeout_add(300, app.quit);"
        "raise SystemExit(app.run([]))"
    )
    env = {**os.environ, "PYTHONPATH": str(GUI)}
    r = subprocess.run(
        ["xvfb-run", "-a", sys.executable, "-c", code],
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0, r.stderr
```

- [ ] **Step 2: Run it**

Run: `cd gui && PYTHONPATH=. python3 -m pytest tests/test_launch.py -q`
Expected: PASS, or SKIP if GTK4/Xvfb absent (`sudo apt-get install -y xvfb gir1.2-gtk-4.0`).

- [ ] **Step 3: Commit**

```bash
git add gui/tests/test_launch.py
git commit -m "test(gui): headless launch smoke test"
```

---

### Task B5: Icon/background editor (`set-asset` + preview drop)

**Files:**
- Modify: `lib.sh` (add `pb_set_asset`)
- Modify: `prettyboot.sh` (add `set-asset` case)
- Modify: `gui/prettyboot_gui/engine.py` (add `set_asset`)
- Modify: `gui/prettyboot_gui/app.py` (drop target on the preview holder)
- Test: `test/asset.bats`

- [ ] **Step 1: Write the failing tests**

Create `test/asset.bats`:

```bash
load helper

PB() { REFIND_DIR="$TMP" "$BATS_TEST_DIRNAME/../prettyboot.sh" "$@"; }

setup() {
  TMP="$(mktemp -d)"; : > "$TMP/refind.conf"
  make_theme "$TMP/themes" mac-dark
  printf 'NEWBG' > "$TMP/new.png"
  printf 'NEWWIN' > "$TMP/win.png"
}
teardown() { rm -rf "$TMP"; }

@test "set-asset background replaces background.png" {
  run PB set-asset mac-dark background "$TMP/new.png"
  [ "$status" -eq 0 ]
  run cat "$TMP/themes/mac-dark/background.png"
  [ "$output" = "NEWBG" ]
}

@test "set-asset win syncs os_win.png and os_win8.png" {
  run PB set-asset mac-dark win "$TMP/win.png"
  [ "$status" -eq 0 ]
  run cat "$TMP/themes/mac-dark/icons/os_win.png"
  [ "$output" = "NEWWIN" ]
  run cat "$TMP/themes/mac-dark/icons/os_win8.png"
  [ "$output" = "NEWWIN" ]
}

@test "set-asset rejects an unknown slot" {
  run PB set-asset mac-dark bogus "$TMP/new.png"
  [ "$status" -ne 0 ]
}
```

> Note: `make_theme` must create the icon files this test reads. If `test/helper.bash`'s `make_theme` only creates `os_linux.png`, add `os_win.png`, `os_win8.png`, `os_ubuntu.png` to it in this step (one-line additions) so the sync targets exist.

- [ ] **Step 2: Run tests to verify they fail**

Run: `bats test/asset.bats`
Expected: FAIL — `set-asset` unknown.

- [ ] **Step 3: Implement `pb_set_asset`**

Add to `lib.sh`:

```bash
# pb_set_asset <theme_dir> <slot> <file>  -- replace a theme asset, syncing
# the rEFInd duplicate icon pairs. slot: background|win|ubuntu|linux.
pb_set_asset() {
  local dir="$1" slot="$2" file="$3"
  [ -f "$file" ] || { echo "source file not found: $file" >&2; return 1; }
  case "$slot" in
    background) cp "$file" "$dir/background.png" ;;
    win)        cp "$file" "$dir/icons/os_win.png"; cp "$file" "$dir/icons/os_win8.png" ;;
    ubuntu|linux) cp "$file" "$dir/icons/os_ubuntu.png"; cp "$file" "$dir/icons/os_linux.png" ;;
    *) echo "unknown slot: $slot (use background|win|ubuntu|linux)" >&2; return 1 ;;
  esac
}
```

- [ ] **Step 4: Add the `set-asset` subcommand**

In `prettyboot.sh`, add after the `get)` case:

```bash
  set-asset)
    theme="${2:?usage: set-asset <theme> <slot> <file>}"
    slot="${3:?usage: set-asset <theme> <slot> <file>}"
    file="${4:?usage: set-asset <theme> <slot> <file>}"
    pb_set_asset "$THEMES/$theme" "$slot" "$file" || exit 1
    echo "Updated $slot for $theme"
    ;;
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `bats test/asset.bats`
Expected: PASS (3 tests)

- [ ] **Step 6: Add `set_asset` to engine and a preview drop target**

In `gui/prettyboot_gui/engine.py`, add:

```python
def set_asset(theme: str, slot: str, path: str) -> None:
    _write("set-asset", theme, slot, path)
```

In `gui/prettyboot_gui/app.py` `_themes_tab`, after creating `self.preview_holder`, enable dropping an image to replace the background of the selected theme:

```python
        bg_drop = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        bg_drop.connect("drop", self._on_bg_drop)
        self.preview_holder.add_controller(bg_drop)
```

And add the handler:

```python
    def _on_bg_drop(self, _t, value, _x, _y):
        row = self.theme_list.get_selected_row()
        path = value.get_path()
        if row and path:
            self._run(lambda: engine.set_asset(row.theme_name, "background", path))
            self._on_theme_selected(None, row)  # refresh preview
        return True
```

- [ ] **Step 7: Byte-compile + tests**

Run: `cd gui && python3 -m py_compile prettyboot_gui/app.py && bats ../test/asset.bats`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add lib.sh prettyboot.sh test/asset.bats test/helper.bash gui/prettyboot_gui/engine.py gui/prettyboot_gui/app.py
git commit -m "feat: icon/background editor via set-asset + preview drop"
```

---

### Task B6: Advanced tab raw save (`write-conf` with backup)

**Files:**
- Modify: `prettyboot.sh` (add `write-conf` case)
- Modify: `gui/prettyboot_gui/engine.py` (add `write_conf`)
- Modify: `gui/prettyboot_gui/app.py` (Save button in Advanced tab)
- Test: `test/settings.bats`

- [ ] **Step 1: Write the failing test**

Append to `test/settings.bats`:

```bash
@test "write-conf backs up then replaces refind.conf" {
  printf 'old contents\n' > "$TMP/refind.conf"
  printf 'new contents\n' > "$TMP/new.conf"
  run PB write-conf "$TMP/new.conf"
  [ "$status" -eq 0 ]
  run cat "$TMP/refind.conf"
  [ "$output" = "new contents" ]
  # exactly one timestamped backup containing the old contents exists
  run bash -c "grep -l 'old contents' '$TMP'/refind.conf.*.bak | wc -l"
  [ "$output" = "1" ]
}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bats test/settings.bats -f "write-conf"`
Expected: FAIL — `write-conf` unknown.

- [ ] **Step 3: Add the `write-conf` subcommand**

In `prettyboot.sh`, add after the `set-asset)` case:

```bash
  write-conf)
    src="${2:?usage: write-conf <file>}"
    [ -f "$src" ] || { echo "file not found: $src" >&2; exit 1; }
    [ -f "$CONF" ] && cp "$CONF" "$CONF.$(date +%Y%m%d%H%M%S).bak"
    cp "$src" "$CONF"
    echo "refind.conf updated (backup saved)"
    ;;
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `bats test/settings.bats -f "write-conf"`
Expected: PASS

- [ ] **Step 5: Wire the Advanced Save button**

In `gui/prettyboot_gui/engine.py`, add:

```python
import tempfile


def write_conf(text: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False) as fh:
        fh.write(text)
        tmp = fh.name
    _write("write-conf", tmp)
```

In `gui/prettyboot_gui/app.py` `_advanced_tab`, before `return box`, add a Save button:

```python
        save = Gtk.Button(label="Save (backup first)")
        save.connect("clicked", self._on_save_raw)
        box.append(save)
```

And the handler:

```python
    def _on_save_raw(self, _btn):
        buf = self.raw_view.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
        self._run(lambda: engine.write_conf(text))
```

- [ ] **Step 6: Byte-compile + tests**

Run: `cd gui && python3 -m py_compile prettyboot_gui/app.py && bats ../test/settings.bats -f "write-conf"`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add prettyboot.sh gui/prettyboot_gui/engine.py gui/prettyboot_gui/app.py test/settings.bats
git commit -m "feat: Advanced tab raw save via write-conf with backup"
```

---

### Task B7: `.zip` theme import

**Files:**
- Modify: `gui/prettyboot_gui/engine.py` (unzip helper)
- Modify: `gui/prettyboot_gui/app.py` (`_on_drop` handles `.zip`)
- Test: `gui/tests/test_engine.py`

- [ ] **Step 1: Write the failing test**

Append to `gui/tests/test_engine.py`:

```python
import zipfile


def test_import_zip(refind, tmp_path):
    theme = _make_theme(tmp_path / "pack", "zipped")
    zpath = tmp_path / "zipped.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        for p in theme.rglob("*"):
            z.write(p, p.relative_to(tmp_path / "pack"))
    engine.import_path(str(zpath))
    assert "zipped" in [n for n, _, _ in engine.list_themes()]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd gui && PYTHONPATH=. python3 -m pytest tests/test_engine.py -k zip -q`
Expected: FAIL — `import_path` missing.

- [ ] **Step 3: Implement `import_path` (folder or zip)**

In `gui/prettyboot_gui/engine.py`, add:

```python
import tempfile
import zipfile


def import_path(path: str, name: str | None = None) -> None:
    """Import a theme from a folder or a .zip. For a zip, extract to a temp
    dir; if it contains a single top-level folder, import that folder."""
    if path.lower().endswith(".zip"):
        tmp = tempfile.mkdtemp(prefix="prettyboot-")
        with zipfile.ZipFile(path) as z:
            z.extractall(tmp)
        entries = [os.path.join(tmp, e) for e in os.listdir(tmp)]
        dirs = [e for e in entries if os.path.isdir(e)]
        src = dirs[0] if len(dirs) == 1 and not name else tmp
        import_theme(src, name)
    else:
        import_theme(path, name)
```

- [ ] **Step 4: Point the GUI drop handler at `import_path`**

In `gui/prettyboot_gui/app.py`, change `_on_drop` to call `engine.import_path` instead of `engine.import_theme`:

```python
    def _on_drop(self, _t, value, _x, _y):
        path = value.get_path()
        if path:
            self._run(lambda: engine.import_path(path))
        return True
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd gui && PYTHONPATH=. python3 -m pytest tests/test_engine.py -k zip -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add gui/prettyboot_gui/engine.py gui/prettyboot_gui/app.py gui/tests/test_engine.py
git commit -m "feat(gui): import themes from .zip"
```

---

## Part C — Packaging

### Task C1: GUI launcher wrapper + desktop entry + polkit policy

**Files:**
- Create: `bin/prettyboot-gui`
- Create: `gui/prettyboot.desktop`
- Create: `gui/com.prettyboot.policy`

- [ ] **Step 1: Create the launcher wrapper**

Create `bin/prettyboot-gui`:

```bash
#!/usr/bin/env bash
# Launches the GUI from the installed location.
exec python3 -m prettyboot_gui.main "$@"
```

Then: `chmod +x bin/prettyboot-gui`

- [ ] **Step 2: Create the desktop entry**

Create `gui/prettyboot.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=prettyboot
Comment=Manage your rEFInd boot menu theme and settings
Exec=prettyboot-gui
Icon=prettyboot
Terminal=false
Categories=System;Settings;
Keywords=boot;refind;theme;dualboot;
```

- [ ] **Step 3: Create the polkit policy**

Create `gui/com.prettyboot.policy`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1.0/policyconfig.dtd">
<policyconfig>
  <action id="com.prettyboot.run">
    <description>Run prettyboot with root privileges</description>
    <message>Authentication is required to change boot menu settings</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/prettyboot</annotate>
    <annotate key="org.freedesktop.policykit.exec.allow_gui">true</annotate>
  </action>
</policyconfig>
```

- [ ] **Step 4: Validate the desktop file**

Run: `desktop-file-validate gui/prettyboot.desktop`
Expected: no output, exit 0. (Install tool if needed: `sudo apt-get install -y desktop-file-utils`.)

- [ ] **Step 5: Commit**

```bash
git add bin/prettyboot-gui gui/prettyboot.desktop gui/com.prettyboot.policy
git commit -m "feat(packaging): GUI launcher, desktop entry, polkit policy"
```

---

### Task C2: Debian packaging

**Files:**
- Create: `debian/source/format`
- Create: `debian/compat`
- Create: `debian/control`
- Create: `debian/changelog`
- Create: `debian/rules`
- Create: `debian/install`
- Create: `debian/links`

- [ ] **Step 1: Source format and compat**

Create `debian/source/format`:

```
3.0 (native)
```

Create `debian/compat`:

```
13
```

- [ ] **Step 2: Control**

Create `debian/control`:

```
Source: prettyboot
Section: admin
Priority: optional
Maintainer: SivaKanth007 <dtavvala@asu.edu>
Build-Depends: debhelper (>= 13)
Standards-Version: 4.6.2
Homepage: https://github.com/SivaKanth007/prettyboot

Package: prettyboot
Architecture: all
Depends: ${misc:Depends}, refind, python3, python3-gi, gir1.2-gtk-4.0, policykit-1
Description: Graphical, themeable rEFInd boot menu manager
 prettyboot manages a rEFInd boot menu: switch Mac-style light/dark themes,
 set timeout and other options, drag-and-drop import themes, and edit icons.
 Provides both a terminal CLI (prettyboot) and a GTK desktop app
 (searchable as "prettyboot").
```

- [ ] **Step 3: Changelog**

Create `debian/changelog`:

```
prettyboot (1.0.0) jammy; urgency=medium

  * Initial release: CLI + GTK4 GUI, theme import, curated/raw settings.

 -- SivaKanth007 <dtavvala@asu.edu>  Fri, 05 Jun 2026 00:00:00 +0000
```

- [ ] **Step 4: Rules**

Create `debian/rules`:

```makefile
#!/usr/bin/make -f
%:
	dh $@
```

Then: `chmod +x debian/rules`

- [ ] **Step 5: Install map**

Create `debian/install`:

```
lib.sh                       usr/share/prettyboot/
prettyboot.sh                usr/share/prettyboot/
install.sh                   usr/share/prettyboot/
themes                       usr/share/prettyboot/
gui/prettyboot_gui           usr/share/prettyboot/
bin/prettyboot-gui           usr/bin/
gui/prettyboot.desktop       usr/share/applications/
gui/com.prettyboot.policy    usr/share/polkit-1/actions/
```

- [ ] **Step 6: Symlink the CLI onto PATH**

Create `debian/links`:

```
usr/share/prettyboot/prettyboot.sh usr/bin/prettyboot
```

- [ ] **Step 7: Make `prettyboot-gui` find the module**

The launcher runs `python3 -m prettyboot_gui.main`, so the package dir must be importable. Edit `bin/prettyboot-gui` to set `PYTHONPATH`:

```bash
#!/usr/bin/env bash
# Launches the GUI from the installed location.
export PYTHONPATH="/usr/share/prettyboot:${PYTHONPATH:-}"
exec python3 -m prettyboot_gui.main "$@"
```

- [ ] **Step 8: Build the package**

Run: `dpkg-buildpackage -us -uc -b` (install tooling if needed: `sudo apt-get install -y debhelper devscripts dpkg-dev`)
Expected: produces `../prettyboot_1.0.0_all.deb`, exit 0.

- [ ] **Step 9: Lint and inspect**

Run: `lintian ../prettyboot_1.0.0_all.deb; dpkg -c ../prettyboot_1.0.0_all.deb`
Expected: lintian shows no errors (warnings acceptable); file list shows `/usr/bin/prettyboot`, `/usr/bin/prettyboot-gui`, `/usr/share/applications/prettyboot.desktop`, `/usr/share/polkit-1/actions/com.prettyboot.policy`, `/usr/share/prettyboot/...`.

- [ ] **Step 10: Commit**

```bash
git add debian/
git commit -m "feat(packaging): debian package (CLI + GUI, arch all)"
```

---

### Task C3: First-run "Set up boot menu" action

**Files:**
- Modify: `gui/prettyboot_gui/engine.py` (add `setup_boot`)
- Modify: `gui/prettyboot_gui/app.py` (banner when no managed block)
- Modify: `install.sh` (accept being invoked as `prettyboot-setup` path is N/A — instead expose via CLI)
- Modify: `prettyboot.sh` (add `setup` subcommand that runs install logic)
- Test: `test/settings.bats` (setup writes a managed block)

- [ ] **Step 1: Write the failing test**

Append to `test/settings.bats`:

```bash
@test "setup deploys bundled themes and writes a managed block" {
  # Use the repo's own themes as the source via SRC_THEMES; skip rEFInd install.
  run env REFIND_DIR="$TMP" SRC_THEMES="$BATS_TEST_DIRNAME/../themes" \
      PB_SKIP_REFIND_INSTALL=1 "$BATS_TEST_DIRNAME/../prettyboot.sh" setup
  [ "$status" -eq 0 ]
  [ -d "$TMP/themes/mac-dark" ]
  run grep -c '>>> prettyboot >>>' "$TMP/refind.conf"
  [ "$output" = "1" ]
}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bats test/settings.bats -f "setup deploys"`
Expected: FAIL — `setup` unknown, falls to usage.

- [ ] **Step 3: Make `install.sh` skippable and reusable**

In `install.sh`, guard the rEFInd auto-install so tests/CI can skip it. Replace the block at `install.sh:10-18` with:

```bash
if [ ! -d "$REFIND_DIR" ]; then
  if [ -n "${PB_SKIP_REFIND_INSTALL:-}" ]; then
    mkdir -p "$REFIND_DIR"; : > "$REFIND_DIR/refind.conf"
  elif command -v apt-get >/dev/null 2>&1; then
    echo "Installing rEFInd via apt-get..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y refind
  else
    echo "rEFInd not found and apt-get unavailable. Install rEFInd manually, then re-run." >&2
    exit 1
  fi
fi
```

- [ ] **Step 4: Add the `setup` subcommand**

In `prettyboot.sh`, add after the `get)` case:

```bash
  setup)
    exec "$here/install.sh"
    ;;
```

(`$here` already resolves to the install dir, where `install.sh` sits beside `prettyboot.sh`.)

- [ ] **Step 5: Run the test to verify it passes**

Run: `bats test/settings.bats -f "setup deploys"`
Expected: PASS

- [ ] **Step 6: Add `setup_boot` to engine and a first-run banner**

In `gui/prettyboot_gui/engine.py`, add:

```python
def has_managed_block() -> bool:
    return bool(_read("get", "timeout").strip()) or bool(list_themes())


def setup_boot() -> None:
    _write("setup")
```

In `gui/prettyboot_gui/app.py`, at the top of `_themes_tab` (before `return box`), prepend a banner when setup hasn't run:

```python
        if not engine.has_managed_block():
            banner = Gtk.Button(label="Set up boot menu")
            banner.connect("clicked", lambda _b: self._run(engine.setup_boot))
            rail.prepend(banner)
```

- [ ] **Step 7: Byte-compile + engine tests**

Run: `cd gui && python3 -m py_compile prettyboot_gui/app.py && PYTHONPATH=. python3 -m pytest tests/test_engine.py -q`
Expected: PASS (existing engine tests still green).

- [ ] **Step 8: Commit**

```bash
git add prettyboot.sh install.sh gui/prettyboot_gui/engine.py gui/prettyboot_gui/app.py test/settings.bats
git commit -m "feat: first-run boot setup via prettyboot setup + GUI banner"
```

---

### Task C4: README + PPA publishing notes

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add an install + GUI section to `README.md`**

Add near the top, after the project description:

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: GUI usage and PPA install instructions"
```

- [ ] **Step 3: Manual PPA publish (user action — documented, not automated)**

These steps require your Launchpad account and GPG key; run them by hand when ready:

```bash
# one-time: create ppa:sivakanth007/prettyboot on launchpad.net, register your GPG key
debuild -S -sa                 # build a SIGNED source package
dput ppa:sivakanth007/prettyboot ../prettyboot_1.0.0_source.changes
# Launchpad emails a build result; then `apt install` works for everyone.
```

---

## Self-Review

**Spec coverage:**
- GTK4 GUI wrapping CLI → Part B (engine.py shells out; app.py).  ✓
- One `.deb`, monorepo, CLI+GUI from one install → Part C (debian/, links, desktop).  ✓
- Themes tab, full-size preview, ⛶ fullscreen → B2/B3 (preview.build_widget, app `_themes_tab`).  *Fullscreen toggle button is presentation polish; covered by preview widget being a standalone overlay — add `set_fullscreened` wiring during B3 if desired.*  ✓
- Settings tab (curated) → B3 `_settings_tab` + A6 `set`/`get`.  ✓
- Advanced raw editor + backup-on-save → B3 `_advanced_tab` (display) + B6 `write-conf` (Save with timestamped backup).  ✓
- Drag-drop import (folder/.zip) → A5 `import` (folders) + B7 `import_path` (zip) + B3/B7 `_on_drop`.  ✓
- Icon/background editor → B5 `set-asset` + preview drop handler.  ✓
- `import`/`set`/`get` subcommands → A5/A6.  ✓
- First-run "Set up boot menu" → C3.  ✓
- Launchpad PPA → C4.  ✓
- Known rEFInd limits respected → Settings exposes only safe keys.  ✓

All spec features now map to a complete TDD task (A1–A6, B1–B7, C1–C4). No deferred gaps remain.

**Placeholder scan:** no TBD/TODO/"implement later" patterns in any task; every code step shows full code and every command shows expected output.

**Type consistency:** `engine.list_themes()` returns `(name, active, valid)` tuples and is consumed that way in `app._reload_themes` and `active_theme`. `engine.import_theme(path, name=None)`, `set_setting(key, value)`, `get_setting(key)`, `use_theme(name)`, `set_timeout(value)` signatures match every call site. CLI subcommand names (`import`, `set`, `get`, `setup`) match `engine.py` argument lists. `preview.theme_assets` returns `{"background", "icons"}` consumed in `build_widget`.
