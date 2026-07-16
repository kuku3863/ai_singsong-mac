#!/usr/bin/env python3
"""
修复 scipy 在 macOS 27+ 上的 Mach-O 兼容性问题。

问题：scipy 预编译 wheel 的 .so 文件中，S_THREAD_LOCAL_ZEROFILL
(类型 0x12) section 的 offset 字段非零，新版 dyld 拒绝加载。

修复：将 zerofill section 的 offset 设为 0，然后重新 ad-hoc 签名。

用法：
    python fix_scipy_macho.py [site-packages 路径]
"""

import struct
import sys
import os
import glob
import subprocess

MAGIC_64 = 0xFEEDFACF
CIGAM_64 = 0xCFFAEDFE
FAT_MAGIC_64 = 0xCAFEBABF
FAT_CIGAM_64 = 0xBFBAFECA
LC_SEGMENT_64 = 0x19

# Section types that are zerofill (from mach-o/loader.h)
ZEROFILL_TYPES = {0x01, 0x12}  # S_ZEROFILL, S_THREAD_LOCAL_ZEROFILL


def fix_macho_slice(data, slice_start, slice_end):
    """Fix sections within one Mach-O slice. Returns True if any changes made."""
    header = struct.unpack_from('<IIIIIIII', data, slice_start)
    magic = header[0]
    if magic not in (MAGIC_64, CIGAM_64):
        return False
    ncmds = header[4]
    fixed = False
    cmd_offset = slice_start + 32  # sizeof(mach_header_64)

    for _ in range(ncmds):
        if cmd_offset + 8 > slice_end:
            break
        cmd, cmdsize = struct.unpack_from('<II', data, cmd_offset)
        if cmd == LC_SEGMENT_64:
            nsects = struct.unpack_from('<I', data, cmd_offset + 64)[0]
            nsects = min(nsects, 1000)
            sect_offset = cmd_offset + 72  # sizeof(segment_command_64)
            for _ in range(nsects):
                if sect_offset + 80 > slice_end:
                    break
                sect_flags = struct.unpack_from('<I', data, sect_offset + 64)[0]
                sect_type = sect_flags & 0xFF
                fileoff = struct.unpack_from('<I', data, sect_offset + 48)[0]
                if sect_type in ZEROFILL_TYPES and fileoff != 0:
                    struct.pack_into('<I', data, sect_offset + 48, 0)
                    segname = data[sect_offset + 16:sect_offset + 32].rstrip(b'\x00').decode('ascii', 'replace')
                    sectname = data[sect_offset:sect_offset + 16].rstrip(b'\x00').decode('ascii', 'replace')
                    print(f"  [{segname}/{sectname}] offset {fileoff} -> 0 (type=0x{sect_type:02x})")
                    fixed = True
                sect_offset += 80  # sizeof(section_64)
        cmd_offset += cmdsize
    return fixed


def fix_file(filepath):
    """Fix one Mach-O file. Returns True if changed."""
    with open(filepath, 'rb') as f:
        data = bytearray(f.read())
    if len(data) < 4:
        return False

    magic = struct.unpack('<I', data[0:4])[0]

    # Handle fat binaries
    if magic in (FAT_MAGIC_64, FAT_CIGAM_64):
        narchs = struct.unpack('>I', data[4:8])[0]
        fixed_any = False
        off = 8
        for _ in range(narchs):
            arch_off = struct.unpack('>I', data[off + 8:off + 12])[0]
            arch_sz = struct.unpack('>I', data[off + 12:off + 16])[0]
            fixed_any |= fix_macho_slice(data, arch_off, arch_off + arch_sz)
            off += 20
        if fixed_any:
            with open(filepath, 'wb') as f:
                f.write(data)
        return fixed_any

    # Single arch thin binary
    if magic in (MAGIC_64, CIGAM_64):
        if fix_macho_slice(data, 0, len(data)):
            with open(filepath, 'wb') as f:
                f.write(data)
            return True
    return False


def find_site_packages():
    """Auto-detect site-packages directory."""
    candidates = glob.glob(os.path.join(
        os.path.dirname(__file__), '.venv', 'lib', 'python*', 'site-packages'))
    if candidates:
        return candidates[0]
    # Fallback: use the Python that's running this script
    for p in sys.path:
        if p.endswith('site-packages'):
            return p
    return None


def main():
    site = sys.argv[1] if len(sys.argv) > 1 else find_site_packages()
    if not site:
        print("ERROR: Cannot find site-packages. Pass path as argument.")
        sys.exit(1)

    pattern = os.path.join(site, 'scipy', '**', '*.so')
    files = glob.glob(pattern, recursive=True)
    if not files:
        print(f"No .so files found in {site}/scipy/")
        sys.exit(1)

    print(f"Scanning {len(files)} .so files in scipy...")
    fixed_files = []
    for f in files:
        if fix_file(f):
            fixed_files.append(f)

    print(f"\nFixed {len(fixed_files)}/{len(files)} files")

    if not fixed_files:
        print("No files needed fixing.")
        return

    # Re-sign fixed files with ad-hoc signature (required by macOS 27+)
    print("\nRe-signing fixed files...")
    for f in fixed_files:
        basename = os.path.basename(f)
        result = subprocess.run(
            ['codesign', '-s', '-', f],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"  ✓ {basename}")
        else:
            print(f"  ✗ {basename}: {result.stderr.strip()}")

    print("\n✅ scipy Mach-O fix complete. The application should now work.")


if __name__ == '__main__':
    main()
