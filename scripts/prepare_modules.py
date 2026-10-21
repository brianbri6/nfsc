#!/usr/bin/env python3
"""Lift the DLLs that run as guest code next to NFSC.exe.

  prepare_modules.py [name ...]      (default: all of them)

Each DLL is read from the player's own copy (the game folder, or the local
DirectX runtime for d3dx9_30), relocated to its fixed guest base, catalogued
from its entry, exports and relocated code pointers, and lifted with its own
prefix into src/recomp/gen_<prefix>. The bases must match guestModuleSpecs in
android/app/src/main/cpp/guest_modules.inc.

Guest layout below the first heap arena (0x01300000):
  NFSC.exe       0x00400000-0x00C2C000
  d3dx9_30.dll   0x00D00000-0x00F60000
  msvcr71.dll    0x00F60000-0x00FB6000
  msvcp71.dll    0x00FC0000-0x0103B000
  palmont.dll    0x01060000-0x011DD000   (NFSCO, tools/nfsco_capture.c)
  NFSCO pool     0x01200000-0x01240000   (palmont's executable allocations)
  logging.dll    0x01240000-0x01268000   (NFSCO)
  server.dll     0x01270000-0x012DF000   (EA's LAN server)

Two filters keep data out of the catalog (as for d3dx9_26 in Most Wanted):
  - a relocated pointer is a seed only if the bytes there probe as a function
    body (jump tables and vtables point into code, string tables do not);
  - a catalogued function containing an instruction that never occurs in this
    compiler's code (arpl, insb, bound, ...) or two `add [eax], al` (zero
    runs) decodes data: it is lifted as RECOMP_UNIMPL. An export another guest
    module imports must not be among them (checked; the script fails).

Everything written here is derived from the binaries and stays in work/ and
src/recomp/gen_* (gitignored). The original files are never written.
"""
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
GAME = pathlib.Path(os.environ.get("NFSC_GAME_ROOT", ROOT.parent / "Need for Speed Carbon"))
SYSTEM = pathlib.Path(os.environ.get("SystemRoot", r"C:\Windows")) / "SysWOW64"
PCRECOMP = pathlib.Path(os.environ.get("PCRECOMP", ROOT.parent / "pcrecomp"))
for sub in ("pe", "disasm"):
    sys.path.insert(0, str(PCRECOMP / "tools" / sub))

# name: (source, guest base, output prefix)
MODULES = {
    "d3dx9_30.dll": (SYSTEM / "d3dx9_30.dll", 0x00D00000, "d3dx_"),
    "msvcr71.dll": (GAME / "msvcr71.dll", 0x00F60000, "msvcr_"),
    "msvcp71.dll": (GAME / "msvcp71.dll", 0x00FC0000, "msvcp_"),
    "server.dll": (GAME / "server.dll", 0x01270000, "server_"),
}
# Modules whose imports of lifted DLLs must resolve to real (non-excluded) code.
IMPORTERS = [GAME / "NFSC.exe"] + [MODULES[n][0] for n in MODULES]

NOT_CODE = {'arpl', 'insb', 'insd', 'insw', 'outsw', 'outsb', 'outsd', 'bound', 'daa', 'das', 'aaa', 'aas',
            'aam', 'aad', 'popaw', 'pushaw', 'sldt', 'lcall', 'ljmp', 'into', 'salc', 'hlt', 'cli', 'sti',
            'iretd', 'int1', 'rdmsr', 'str', 'les', 'lds', 'rsm', 'lldt', 'lsl', 'bnd',
            'loop', 'loopne', 'loope', 'in', 'out'}   # MSVC never emits loop*; Win32 code no port I/O


def run(script, *arguments):
    subprocess.run([sys.executable, str(ROOT / "scripts" / script), *(str(a) for a in arguments)],
                   cwd=ROOT, check=True)


def probe_seeds(image, seeds_path, out_path):
    from pe_analyze import analyze_pe
    from disasm32 import Disassembler
    info = analyze_pe(str(image))
    dis = Disassembler(open(image, "rb").read(), info.image_base, info.sections)
    seeds = json.load(open(seeds_path))
    keep = [e for e in seeds if not e["note"].startswith("relocated") or dis.probes_as_function_body(e["address"])]
    json.dump(keep, open(out_path, "w"), indent=1)
    print(f"[*] {image.name}: {len(seeds)} seeds, {len(keep)} after probing relocated pointers")


def imported_names(dll):
    import pefile
    names = set()
    for path in IMPORTERS:
        pe = pefile.PE(str(path), fast_load=True)
        pe.parse_data_directories([pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
        for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
            if entry.dll.decode().lower() == dll:
                names |= {i.name.decode() if i.name else f"#{i.ordinal}" for i in entry.imports}
    return names


def not_code(image, catalog_path, base, dll, out_path):
    import pefile
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    pe = pefile.PE(str(image))
    img = pe.get_memory_mapped_image()
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    bad = []
    for f in json.load(open(catalog_path))["functions"]:
        zeros, data = 0, False
        for start, end, *_ in f["blocks"]:
            for ins in md.disasm(img[start - base:end - base], start):
                if ins.mnemonic.split()[-1] in NOT_CODE:
                    data = True
                    break
                zeros += ins.bytes[:2] == b"\x00\x00"
            if data:
                break
        if data or zeros >= 2:
            bad.append(f["address"])
    exports = {}
    for e in getattr(pe, "DIRECTORY_ENTRY_EXPORT", None).symbols if hasattr(pe, "DIRECTORY_ENTRY_EXPORT") else []:
        va = base + e.address
        if e.name:
            exports[e.name.decode()] = va
        exports[f"#{e.ordinal}"] = va
    wanted = {n: exports[n] for n in imported_names(dll) if n in exports}
    hit = sorted(n for n, va in wanted.items() if va in set(bad))
    if hit:
        sys.exit(f"{dll}: imported exports classified as data: {hit}")
    json.dump(bad, open(out_path, "w"))
    print(f"[*] {dll}: {len(bad)} catalogued starts decode data; {len(wanted)} imported exports are clean")


def lift(name):
    source, base, prefix = MODULES[name]
    if not source.is_file():
        sys.exit(f"{name}: {source} not found (use your own copy; nothing is downloaded)")
    tag = prefix.rstrip("_")
    work = ROOT / "work" / "modules" / tag
    work.mkdir(parents=True, exist_ok=True)
    image, seeds, probed = work / f"{prefix}relocated.dll", work / "seeds.json", work / "seeds_probed.json"
    catalog, data = work / "catalog.json", work / "not_code.json"
    run("prepare_module.py", source, hex(base), image, seeds)
    probe_seeds(image, seeds, probed)
    run("run_lift.py", "catalog", image, probed, catalog, "--seeds-only")
    not_code(image, catalog, base, name, data)
    run("run_lift.py", "lift", image, catalog, ROOT / "src/recomp" / f"gen_{tag}", "--prefix", prefix, "--exclude", data)


if __name__ == "__main__":
    names = sys.argv[1:] or list(MODULES)
    unknown = [n for n in names if n not in MODULES]
    if unknown:
        sys.exit(f"unknown module(s) {unknown}; known: {list(MODULES)}")
    for n in names:
        lift(n)
