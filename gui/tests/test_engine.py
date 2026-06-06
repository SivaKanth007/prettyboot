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
