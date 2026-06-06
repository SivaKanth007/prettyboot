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
