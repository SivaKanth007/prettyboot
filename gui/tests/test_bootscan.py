from pathlib import Path

from prettyboot_gui import bootscan


def _touch(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")


def _fake_esp(tmp_path: Path) -> Path:
    """Replica of the user's real ESP layout (ground truth in the plan)."""
    efi = tmp_path / "EFI"
    _touch(efi / "Microsoft" / "Boot" / "bootmgfw.efi")
    _touch(efi / "Microsoft" / "Boot" / "bootmgr.efi")
    _touch(efi / "Microsoft" / "Boot" / "memtest.efi")
    _touch(efi / "ubuntu" / "shimx64.efi")
    _touch(efi / "ubuntu" / "grubx64.efi")
    _touch(efi / "ubuntu" / "mmx64.efi")
    _touch(efi / "Boot" / "bootx64.efi")
    _touch(efi / "Boot" / "fbx64.efi")
    _touch(efi / "Boot" / "mmx64.efi")
    _touch(efi / "refind" / "refind_x64.efi")
    for icon in ("os_unknown.png", "func_about.png", "func_hidden.png",
                 "func_shutdown.png", "func_reset.png", "func_firmware.png",
                 "tool_mok_tool.png"):
        _touch(efi / "refind" / "icons" / icon)
    return efi


def test_scan_entries_matches_real_menu(tmp_path):
    efi = _fake_esp(tmp_path)
    entries = bootscan.scan_entries(str(efi), str(efi / "refind"), "SYSTEM")
    keys = [e["key"] for e in entries]
    # user's real menu: windows, ubuntu, then the fallback pair
    assert keys == ["win", "linux", "linux", "unknown"]
    assert entries[0]["label"] == "Boot Microsoft EFI boot from SYSTEM"
    assert entries[1]["label"] == "Boot ubuntu from SYSTEM"


def test_scan_entries_excludes_refind_and_tools(tmp_path):
    efi = _fake_esp(tmp_path)
    entries = bootscan.scan_entries(str(efi), str(efi / "refind"), "SYSTEM")
    labels = " ".join(e["label"] for e in entries)
    assert "refind" not in labels.lower()
    assert "mm" not in labels.lower()          # MokManager not an entry
    assert "bootmgr " not in labels.lower()    # only bootmgfw for Microsoft
    assert "memtest" not in labels.lower()
    assert "grub" not in labels.lower()        # shim supersedes grub


def test_scan_entries_no_volume_label(tmp_path):
    efi = _fake_esp(tmp_path)
    entries = bootscan.scan_entries(str(efi), str(efi / "refind"), "")
    assert entries[0]["label"] == "Boot Microsoft EFI boot"


def test_scan_entries_missing_root(tmp_path):
    assert bootscan.scan_entries(str(tmp_path / "nope"), str(tmp_path), "X") == []
