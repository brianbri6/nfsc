#!/usr/bin/env python3
"""Verify the owner's Carbon 1.4 PE32 binaries and 285 sound banks offline.

Requires Python 3 only. Reads game files without running or modifying them.
Reports metadata, counts and hashes, never any game code or assets.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

EXPECTED_EXE_SHA256 = "baaaaec33873d4ba7e4dbae6a5212049ffdcf9679a35d865d7625b4189952fd3"
EXPECTED_LAYOUTS = {
    "NFSC.exe": (0x00400000, 0x0082B34E),
    "d3dx9_30.dll": (0x00400000, 0x00260000),
    "msvcr71.dll": (0x7C340000, 0x00056000),
    "msvcp71.dll": (0x7C3A0000, 0x0007B000),
}
CALL_TABLE = 0x00A7D6C0
GAME_CODE_LO, GAME_CODE_HI = 0x00401000, 0x009C1000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parse_pe(file, include_image=False):
    data = file.read_bytes()
    require(len(data) >= 256 and data[:2] == b"MZ", f"{file.name}: missing MZ header")
    off = struct.unpack_from("<I", data, 0x3C)[0]
    require(off + 24 + 96 <= len(data) and data[off:off + 4] == b"PE\x00\x00",
            f"{file.name}: invalid PE signature")
    machine, sections, _, _, _, optional_bytes, _ = struct.unpack_from("<HHIIIHH", data, off + 4)
    opt = off + 24
    magic, = struct.unpack_from("<H", data, opt)
    require(machine == 0x14C and magic == 0x10B, f"{file.name}: expected x86 PE32")
    base = struct.unpack_from("<I", data, opt + 28)[0]
    size = struct.unpack_from("<I", data, opt + 56)[0]
    headers = struct.unpack_from("<I", data, opt + 60)[0]
    require(0 < headers <= len(data) and 0 < size < 100_000_000,
            f"{file.name}: invalid PE image size")
    details = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
               "image_base": f"0x{base:08x}", "size_of_image": f"0x{size:08x}"}
    if not include_image:
        return details, None
    image = bytearray(size)
    image[:headers] = data[:headers]
    table = opt + optional_bytes
    for i in range(sections):
        at = table + i * 40
        require(at + 40 <= len(data), f"{file.name}: truncated PE section table")
        _, rva, raw_size, pointer = struct.unpack_from("<IIII", data, at + 8)
        require(rva < size and pointer + raw_size <= len(data),
                f"{file.name}: invalid section mapping")
        copied = min(raw_size, size - rva)  # raw section padding may exceed SizeOfImage
        image[rva:rva + copied] = data[pointer:pointer + copied]
    return details, image


def verify(game_root, d3dx_path=None):
    root = Path(game_root).expanduser().resolve()
    report = {"source_directory": str(root), "game_executable": {},
              "required_dlls": {}, "sound_banks": {}}
    image = None
    for name, (base, size) in EXPECTED_LAYOUTS.items():
        path = Path(d3dx_path).expanduser().resolve() if name == "d3dx9_30.dll" and d3dx_path else root / name
        require(path.is_file(), f"Required file missing: {path}")
        details, mapped = parse_pe(path, include_image=name == "NFSC.exe")
        require(int(details["image_base"], 16) == base and
                int(details["size_of_image"], 16) == size,
                f"{name}: unexpected PE image base or size")
        if name == "NFSC.exe":
            require(details["sha256"] == EXPECTED_EXE_SHA256,
                    f"NFSC.exe checksum differs: {details['sha256']}")
            report["game_executable"], image = details, mapped
        else:
            report["required_dlls"][name] = details

    banks = sorted((root / "SOUND").rglob("*.abk"))
    require(banks, "No SOUND/**/*.abk files found")
    distinct, table_indices = set(), set()
    refs, code_bytes = 0, 0
    for path in banks:
        data = path.read_bytes()
        name = str(path.relative_to(root))
        require(len(data) >= 0x8C and data[:4] == b"ABKC",
                f"{name}: invalid ABKC header")
        start, end = struct.unpack_from("<II", data, 0x84)
        table, = struct.unpack_from("<I", data, 0x30)
        require(0 < start < end <= len(data) and table + 4 <= len(data),
                f"{name}: invalid code/call bounds")
        count, = struct.unpack_from("<I", data, table)
        require(count <= (len(data) - table - 4) // 4,
                f"{name}: call list exceeds file bounds")
        entries = struct.unpack_from(f"<{count}I", data, table + 4)
        offsets = []
        for absolute in entries:
            offset = absolute - start
            require(0 <= offset <= end - start - 4 and data[start + offset - 1] == 0xE8,
                    f"{name}: invalid x86 call operand at {absolute:#x}")
            index, = struct.unpack_from("<I", data, absolute)
            slot = CALL_TABLE - 0x00400000 + index * 4
            require(0 <= slot <= len(image) - 4,
                    f"{name}: call table index {index} outside the game image")
            target, = struct.unpack_from("<I", image, slot)
            require(GAME_CODE_LO <= target < GAME_CODE_HI,
                    f"{name}: invalid game call target {target:#x} at index {index}")
            offsets.append(offset)
            table_indices.add(index)
        require(count <= 65535 and max(offsets, default=0) <= 65535,
                f"{name}: code block relocation offsets exceed 16-bit storage")
        digest = hashlib.sha1(data[start:end] + struct.pack(f"<{count}H", *offsets)).hexdigest()
        distinct.add(digest)
        refs += count
        code_bytes += end - start
    report["sound_banks"] = {
        "total_banks": len(banks),
        "unique_code_blocks": len(distinct),
        "total_embedded_code_bytes_including_duplicates": code_bytes,
        "patched_call_references_verified": refs,
        "unique_game_call_table_entries": len(table_indices),
        "status": "all ABKC structure/call-index/target checks passed",
    }
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("game_root", type=Path)
    p.add_argument("--json-out", type=Path)
    p.add_argument("--d3dx", type=Path, help="Optional separate local d3dx9_30.dll")
    args = p.parse_args()
    try:
        report = verify(args.game_root, args.d3dx)
    except (OSError, ValueError, struct.error) as e:
        p.exit(1, f"Input verification FAILED: {e}\n")
    value = json.dumps(report, indent=2)
    print(value)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(value + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
