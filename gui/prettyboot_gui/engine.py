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


def set_asset(theme: str, slot: str, path: str) -> None:
    _write("set-asset", theme, slot, path)
