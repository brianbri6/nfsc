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
import hashlib
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
    "d3dx9_30.dll": (pathlib.Path(os.environ.get("NFSC_D3DX_PATH", str(SYSTEM / "d3dx9_30.dll"))), 0x00D00000, "d3dx_"),
    "msvcr71.dll": (GAME / "msvcr71.dll", 0x00F60000, "msvcr_"),
    "msvcp71.dll": (GAME / "msvcp71.dll", 0x00FC0000, "msvcp_"),
    "server.dll": (GAME / "server.dll", 0x01270000, "server_"),
}
# Only modules selected for this build may impose import/export
# requirements. The default offline path explicitly omits server.dll.
# In particular, never require or parse LAN/online DLLs for single-player.
# Keep the importer set stable when --resume asks for only missing DLLs.
# msvcp71 may depend on msvcr71 even when the latter lift already finished.
# The EA LAN DLL is considered only when explicitly selected.
SELECTED = [n for n in sys.argv[1:] if n != "--resume"]
BASE_IMPORTERS = ("d3dx9_30.dll", "msvcr71.dll", "msvcp71.dll")
IMPORTERS = [GAME / "NFSC.exe"] + [MODULES[n][0] for n in BASE_IMPORTERS]
if "server.dll" in SELECTED:
    IMPORTERS.append(MODULES["server.dll"][0])

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



def _sha256(path):
    """Streaming binary digest; avoid loading DLLs into memory a second time."""
    hash_value = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            hash_value.update(part)
    return hash_value.hexdigest()


def _json_valid(path, key=None):
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return key is None or (isinstance(obj, dict) and key in obj)
    except (OSError, ValueError):
        return False


def _checkpoint_id(source, base, name):
    # Importers affect the required-export validation; do not reuse one
    # module's catalog from a different game version or recompiler.
    dependencies = [source, *IMPORTERS, ROOT / "scripts/prepare_module.py",
                    ROOT / "scripts/prepare_modules.py",
                    ROOT / "scripts/run_lift.py", ROOT / "scripts/mw_lifter.py",
                    PCRECOMP / "tools/pe/pe_analyze.py",
                    PCRECOMP / "tools/disasm/disasm32.py",
                    PCRECOMP / "tools/lift/lift32.py"]
    value = hashlib.sha256(f"{name}:{base:08X}:v2".encode("ascii"))
    for item in dependencies:
        if not item.is_file():
            raise FileNotFoundError(f"Missing dependency for {name}: {item}")
        value.update(item.name.encode("utf-8"))
        value.update(_sha256(item).encode("ascii"))
    return value.hexdigest()


def lift_complete(generated, prefix):
    stats = generated / f"{prefix}lift_stats.json"
    dispatch = generated / f"{prefix}recomp_dispatch.c"
    if not (_json_valid(stats, "functions") and dispatch.is_file()):
        return False
    data = json.loads(stats.read_text(encoding="utf-8"))
    count = len(list(generated.glob(f"{prefix}recomp_[0-9][0-9][0-9][0-9].c")))
    return (data.get("functions", 0) > 0 and
            data.get("lift_failures", 1) == 0 and
            data.get("files") == count)


def lift(name, resume=False):
    source, base, prefix = MODULES[name]
    if not source.is_file():
        sys.exit(f"{name}: {source} not found (use your own copy; nothing is downloaded)")
    tag = prefix.rstrip("_")
    work = ROOT / "work" / "modules" / tag
    work.mkdir(parents=True, exist_ok=True)
    image = work / f"{prefix}relocated.dll"
    seeds, probed = work / "seeds.json", work / "seeds_probed.json"
    catalog, excluded = work / "catalog.json", work / "not_code.json"
    generated = ROOT / "src/recomp" / f"gen_{tag}"
    manifest = work / "pipeline_checkpoint.json"
    fingerprint = _checkpoint_id(source, base, name)

    checkpoint = {}
    if resume and _json_valid(manifest, "fingerprint"):
        checkpoint = json.loads(manifest.read_text(encoding="utf-8"))
    previous = checkpoint.get("completed", []) if checkpoint.get("fingerprint") == fingerprint else []
    stages = []

    def save(stage):
        stages.append(stage)
        value = {"fingerprint": fingerprint, "source_sha256": _sha256(source),
                 "completed": list(stages)}
        tmp = manifest.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        tmp.replace(manifest)
        print(f"CHECKPOINT {name}: {stage}", flush=True)

    def skip(stage, valid):
        if resume and stage in previous and valid:
            print(f"RESUME {name}: {stage} completed", flush=True)
            stages.append(stage)
            return True
        return False

    # Any invalid intermediate result invalidates that stage and successors.
    if not skip("relocated", image.is_file() and _json_valid(seeds)):
        run("prepare_module.py", source, hex(base), image, seeds)
        previous = []
        save("relocated")

    if not skip("probed", _json_valid(probed)):
        probe_seeds(image, seeds, probed)
        previous = []
        save("probed")

    if not skip("catalogued", _json_valid(catalog, "functions")):
        run("run_lift.py", "catalog", image, probed, catalog, "--seeds-only")
        if not _json_valid(catalog, "functions"):
            raise RuntimeError(f"{name}: catalog output is missing/invalid")
        previous = []
        save("catalogued")

    if not skip("classified", _json_valid(excluded)):
        not_code(image, catalog, base, name, excluded)
        if not _json_valid(excluded):
            raise RuntimeError(f"{name}: code exclusion list missing/invalid")
        previous = []
        save("classified")

    if not skip("lifted", lift_complete(generated, prefix)):
        run("run_lift.py", "lift", image, catalog, generated,
            "--prefix", prefix, "--exclude", excluded)
        if not lift_complete(generated, prefix):
            raise RuntimeError(f"{name}: generated C files/manifest incomplete")
        save("lifted")


if __name__ == "__main__":
    names = SELECTED or list(MODULES)
    unknown = [n for n in names if n not in MODULES]
    if unknown:
        sys.exit(f"unknown module(s) {unknown}; known: {list(MODULES)}")
    for n in names:
        lift(n, resume="--resume" in sys.argv[1:])
