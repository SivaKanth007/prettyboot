#!/usr/bin/env bash
# capture.sh <theme-name> [out.png] - boot real rEFInd with a bundled theme in
# QEMU+OVMF and screenshot the boot menu. DEV TOOL ONLY (not shipped, not CI).
# Requires: qemu-system-x86, ovmf, mtools, dosfstools, imagemagick.
set -euo pipefail
theme="${1:?usage: capture.sh <theme-name> [out.png]}"
repo="$(cd "$(dirname "$0")/../.." && pwd)"
out="${2:-$repo/docs/calibration/$theme.png}"
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT

# 1. find a readable rEFInd EFI binary (local install, refind package, or apt)
efi=""
for c in /boot/efi/EFI/refind/refind_x64.efi \
         /usr/share/refind/refind/refind_x64.efi; do
  [ -r "$c" ] && efi="$c" && break
done
if [ -z "$efi" ]; then
  (cd "$work" && apt-get download refind >/dev/null \
    && dpkg-deb -x refind_*.deb x)
  efi="$work/x/usr/share/refind/refind/refind_x64.efi"
fi

# 2. stage ESP contents: rEFInd as the default boot app + theme + manual
#    menu entries (loaders are dummies; rEFInd only needs them to exist)
esp="$work/esp"
mkdir -p "$esp/EFI/BOOT/themes" "$esp/dummy"
cp "$efi" "$esp/EFI/BOOT/BOOTX64.EFI"
# rEFInd's built-in tool/OS icons live in an icons/ dir next to the binary;
# without it every icon falls back to the striped dummy image.
for d in "$(dirname "$efi")/icons" /usr/share/refind/refind/icons; do
  [ -d "$d" ] && cp -r "$d" "$esp/EFI/BOOT/icons" && break
done
cp -r "$repo/themes/$theme" "$esp/EFI/BOOT/themes/$theme"
printf 'x' > "$esp/dummy/linux.efi"
printf 'x' > "$esp/dummy/windows.efi"
cat > "$esp/EFI/BOOT/refind.conf" <<EOF
timeout 0
resolution 1024 768
scanfor manual
include themes/$theme/theme.conf
menuentry "Ubuntu" {
    icon /EFI/BOOT/themes/$theme/icons/os_linux.png
    loader /dummy/linux.efi
}
menuentry "Windows" {
    icon /EFI/BOOT/themes/$theme/icons/os_win8.png
    loader /dummy/windows.efi
}
EOF

# 3. FAT ESP image via mtools (no mount, no sudo)
img="$work/esp.img"
truncate -s 64M "$img"
mkfs.vfat "$img" >/dev/null
mcopy -i "$img" -s "$esp"/* ::/

# 4. OVMF firmware
ovmf=""
for c in /usr/share/ovmf/OVMF.fd /usr/share/OVMF/OVMF.fd; do
  [ -f "$c" ] && ovmf="$c" && break
done
[ -n "$ovmf" ] || { echo "OVMF.fd not found; install ovmf" >&2; exit 1; }

# 5. boot headless, screendump after rEFInd settles, quit
mkdir -p "$(dirname "$out")"
{ sleep 15; echo "screendump $work/shot.ppm"; sleep 2; echo quit; } | \
  qemu-system-x86_64 -bios "$ovmf" -m 512 \
    -drive file="$img",format=raw,if=ide \
    -display none -serial none -monitor stdio >/dev/null
convert "$work/shot.ppm" "$out"
echo "wrote $out"
