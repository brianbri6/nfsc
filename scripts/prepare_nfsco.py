#!/usr/bin/env python3
"""Prepare the NFSCO online mod (nfsco.club) as lifted guest code.

  prepare_nfsco.py <capture dir>        (tools/nfsco_capture.exe output, e.g. work/nfsco_patches_v3)

NFSCO's palmont.dll patches NFSC.exe in memory (OnAttach): jumps into itself
and into trampolines it allocates, plus instruction and data edits. Lifted
code cannot follow bytes written at run time, so the capture made on Windows
with the guest layout (palmont 0x01060000, trampoline pool 0x01200000,
logging.dll 0x01240000) is turned into:

  work/nfsco/nfsco.analysis.exe   NFSC.exe's analysis copy with every captured
                                  patch applied; it replaces work/speed.analysis.exe
                                  as the lift input (src/recomp/gen)
  src/recomp/gen_palmont          palmont.dll relocated to 0x01060000
  src/recomp/gen_logging          logging.dll relocated to 0x01240000
  src/recomp/gen_pool             the trampoline pool (64-byte slots, MinHook
                                  layout) as code at 0x01200000

At run time palmont's OnAttach runs translated and writes the same patches;
its executable allocations are served from the pool in the captured order.
The NFSCO authors allowed translating their binaries for this port; nothing
here is committed (work/ and src/recomp/gen_* are gitignored).
"""
import json
import os
import pathlib
import struct
import subprocess
import sys

import pefile

ROOT = pathlib.Path(__file__).resolve().parent.parent
GAME = pathlib.Path(os.environ.get("NFSC_GAME_ROOT", ROOT.parent / "Need for Speed Carbon"))
WORK = ROOT / "work" / "nfsco"
POOL_BASE, POOL_SIZE, SLOT = 0x01200000, 0x40000, 64
MODULES = {  # name: (source, guest base, prefix)
    "palmont.dll": (GAME / "NFSCO" / "bin" / "palmont.dll", 0x01060000, "palmont_"),
    "logging.dll": (GAME / "logging.dll", 0x01240000, "logging_"),
}


def run(script, *arguments):
    subprocess.run([sys.executable, str(ROOT / "scripts" / script), *(str(a) for a in arguments)], cwd=ROOT, check=True)


def read_patches(capture):
    """(va, patched bytes, [kind, target]); the bytes come from image.bin (the
    report truncates long ranges), checked against the report's prefix."""
    image = (capture / "image.bin").read_bytes()
    out = []
    for line in (capture / "patches.txt").read_text().splitlines():
        parts = line.split()
        va, size, shown = int(parts[0], 16), int(parts[1]), bytes.fromhex(parts[4])
        new = image[va - 0x400000:va - 0x400000 + size]
        if len(new) != size or not new.startswith(shown):
            sys.exit(f"patch does not match image.bin: {line}")
        out.append((va, new, parts[5:]))
    return out


def patched_exe(capture):
    source = ROOT / "work" / "speed.analysis.exe"
    pe = pefile.PE(str(source), fast_load=True)
    base, data = pe.OPTIONAL_HEADER.ImageBase, bytearray(source.read_bytes())
    applied = skipped = 0
    for va, new, _ in read_patches(capture):
        try:
            off = pe.get_offset_from_rva(va - base)
        except pefile.PEFormatError:
            off = None
        section = pe.get_section_by_rva(va - base)
        if off is None or section is None or va - base + len(new) > section.VirtualAddress + section.SizeOfRawData:
            skipped += 1   # uninitialized data: palmont writes it at run time
            continue
        data[off:off + len(new)] = new
        applied += 1
    out = WORK / "nfsco.analysis.exe"
    out.write_bytes(bytes(data))
    print(f"[*] {applied} patches applied to the analysis copy, {skipped} in uninitialized data -> {out}")
    return out


def pool_module(capture):
    """The trampoline pool as a minimal PE32 at POOL_BASE; seeds: every used slot."""
    code = (capture / "pool.bin").read_bytes()
    if len(code) > POOL_SIZE:
        sys.exit("pool larger than its reservation")
    seeds = [{"address": POOL_BASE + i, "note": "nfsco pool slot"} for i in range(0, len(code), SLOT) if any(code[i:i + SLOT])]
    targets = {int(p[2][-1], 16) for p in read_patches(capture) if len(p[2]) == 2 and p[2][0] in ("jmp", "call")}
    missing = [hex(t) for t in targets if POOL_BASE <= t < POOL_BASE + len(code) and (t - POOL_BASE) % SLOT]
    if missing:
        sys.exit(f"patch targets inside pool slots not at a slot start: {missing}")
    text_rva, size = 0x1000, len(code)
    image_size = text_rva + ((size + 0xFFF) & ~0xFFF)
    hdr = bytearray(0x1000)
    struct.pack_into("<2s58xI", hdr, 0, b"MZ", 0x40)
    struct.pack_into("<4sHHIIIHH", hdr, 0x40, b"PE\0\0", 0x14C, 1, 0, 0, 0, 0xE0, 0x2102)
    struct.pack_into("<HBBIIIIIIIIIHHHHHHIIIIHHIIIIII", hdr, 0x58, 0x10B, 1, 0, size, 0, 0, 0, text_rva, 0,
                     POOL_BASE - text_rva, 0x1000, 0x1000, 4, 0, 0, 0, 4, 0, 0, image_size, 0x1000, 0, 2, 0,
                     0x100000, 0x1000, 0x100000, 0x1000, 0, 16)
    struct.pack_into("<8sIIIIIIHHI", hdr, 0x58 + 0xE0, b".text", size, text_rva, size, 0x1000, 0, 0, 0, 0, 0x60000020)
    dll = WORK / "pool.analysis.dll"
    dll.write_bytes(bytes(hdr) + code)
    seeds_path = WORK / "pool_seeds.json"
    json.dump(seeds, open(seeds_path, "w"), indent=1)
    print(f"[*] pool: {len(code):#x} bytes, {len(seeds)} used slots -> {dll}")
    return dll, seeds_path


def main(capture):
    capture = pathlib.Path(capture).resolve()
    WORK.mkdir(parents=True, exist_ok=True)
    modules = (capture / "modules.txt").read_text()
    for need in ("palmont.dll 01060000", "logging.dll 01240000", "pool 01200000"):
        if need not in modules:
            sys.exit(f"capture was not made with the guest layout ({need} missing in modules.txt)")
    patched_exe(capture)
    dll, seeds = pool_module(capture)
    run("run_lift.py", "catalog", dll, seeds, WORK / "pool_catalog.json", "--seeds-only")
    run("run_lift.py", "lift", dll, WORK / "pool_catalog.json", ROOT / "src/recomp/gen_pool", "--prefix", "pool_")
    for name, (source, base, prefix) in MODULES.items():
        tag = prefix.rstrip("_")
        image, seeds = WORK / f"{tag}.relocated.dll", WORK / f"{tag}_seeds.json"
        run("prepare_module.py", source, hex(base), image, seeds)
        run("run_lift.py", "catalog", image, seeds, WORK / f"{tag}_catalog.json", "--seeds-only")
        run("run_lift.py", "lift", image, WORK / f"{tag}_catalog.json", ROOT / "src/recomp" / f"gen_{tag}", "--prefix", prefix)
    lift_game()


def continuations():
    """Game addresses palmont's hooks and trampolines return to with
    `push imm32; ret` (lift32 turns that into a jump): each must be a lifted
    entry of the patched NFSC.exe, although it is the middle of a function."""
    import re
    found = set()
    for tag in ("palmont", "pool"):
        for c in (ROOT / "src/recomp" / f"gen_{tag}").glob(f"{tag}_recomp_*.c"):
            for m in re.finditer(r"RECOMP_ITAIL\(0x([0-9A-F]{8})u\); (?:return;|RECOMP_RETURN\(\);) /\* push/ret jump", c.read_text()):
                va = int(m.group(1), 16)
                if 0x401000 <= va < 0x9C1000:
                    found.add(va)
    return sorted(found)


def lift_game():
    """Catalog and lift the patched NFSC.exe into src/recomp/gen, with the
    usual code seeds plus the hook continuations."""
    seeds = json.load(open(ROOT / "work" / "seeds_code.json"))
    extra = continuations()
    seeds += [{"address": va, "note": "nfsco hook continuation"} for va in extra]
    path = WORK / "nfsc_seeds.json"
    json.dump(seeds, open(path, "w"), indent=1)
    print(f"[*] {len(extra)} hook continuations added to the NFSC.exe seeds")
    exe, catalog = WORK / "nfsco.analysis.exe", WORK / "catalog.json"
    run("run_lift.py", "catalog", exe, path, catalog)
    starts = {f["address"] for f in json.load(open(catalog))["functions"]}
    missing = [hex(va) for va in extra if va not in starts]
    if missing:
        sys.exit(f"hook continuations missing from the catalog: {missing}")
    out = ROOT / "src/recomp/gen"
    if out.exists():
        import shutil
        shutil.rmtree(out)
    run("run_lift.py", "lift", exe, catalog, out)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
