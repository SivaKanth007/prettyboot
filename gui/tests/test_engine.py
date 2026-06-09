import os
import subprocess
import tempfile
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


import zipfile


def test_import_zip(refind, tmp_path):
    theme = _make_theme(tmp_path / "pack", "zipped")
    zpath = tmp_path / "zipped.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        for p in theme.rglob("*"):
            z.write(p, p.relative_to(tmp_path / "pack"))
    engine.import_path(str(zpath))
    assert "zipped" in [n for n, _, _ in engine.list_themes()]


def test_import_zip_with_name(refind, tmp_path):
    theme = _make_theme(tmp_path / "pack", "original")
    zpath = tmp_path / "original.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        for p in theme.rglob("*"):
            z.write(p, p.relative_to(tmp_path / "pack"))
    engine.import_path(str(zpath), name="renamed")
    themes = {n: valid for n, _, valid in engine.list_themes()}
    assert themes.get("renamed") is True


def test_write_failure_surfaces_stderr(refind):
    with pytest.raises(RuntimeError, match="not found"):
        engine.set_asset("nope", "background", "/nonexistent/file.png")


def test_write_conf_cleans_temp_file(refind, monkeypatch):
    created = []
    real = tempfile.mkstemp

    def spy(*a, **k):
        fd, path = real(*a, **k)
        created.append(path)
        return fd, path

    monkeypatch.setattr(engine.tempfile, "mkstemp", spy)
    engine.write_conf("timeout 5\n")
    assert (refind / "refind.conf").read_text() == "timeout 5\n"
    assert created and not os.path.exists(created[0])
