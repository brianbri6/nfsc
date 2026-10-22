#!/usr/bin/env python3
"""Generate Carbon's stock single-player C code without the NFSCO online mod.

Usage:
  python scripts/prepare_offline.py --game-root "../Need for Speed Carbon" \
      --d3dx "C:/Windows/SysWOW64/d3dx9_30.dll"
  python scripts/prepare_offline.py --game-root "../Need for Speed Carbon" --check-only

Requires the exact NFSC.exe named in config/reference.json, game runtime DLLs,
the game's SOUND/**/*.abk banks and the patched sibling pcrecomp checkout.
Generated artifacts remain local and gitignored. No game files are modified.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = json.loads((ROOT / "config" / "reference.json").read_text(encoding="utf-8"))
REQUIRED_DLLS = ("msvcr71.dll", "msvcp71.dll")
PCRECOMP_FILES = ("tools/pe/pe_analyze.py", "tools/disasm/disasm32.py",
                  "runtime/recomp32/recomp_types.h")


def run(env, *command):
    print("+", " ".join(map(str, command)), flush=True)
    subprocess.run([str(item) for item in command], cwd=ROOT, env=env, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path,
                        default=Path(os.environ.get("NFSC_GAME_ROOT", ROOT.parent / "Need for Speed Carbon")),
                        help="Path to the extracted original PC Carbon 1.4 game directory")
    parser.add_argument("--d3dx", type=Path, default=None,
                        help="Path to the 32-bit d3dx9_30.dll (Windows SysWOW64 or your own local copy)")
    parser.add_argument("--check-only", action="store_true",
                        help="Validate inputs without generating any C code")
    args = parser.parse_args()
    game = args.game_root.expanduser().resolve()
    pcrecomp = Path(os.environ.get("PCRECOMP", ROOT.parent / "pcrecomp")).expanduser().resolve()
    system = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    # Copies of the original game may ship d3dx9_30.dll beside NFSC.exe.
    # Prefer that local copy when no explicit override is set.
    explicit_d3dx = args.d3dx or os.environ.get("NFSC_D3DX_PATH")
    fallback_d3dx = game / "d3dx9_30.dll" if (game / "d3dx9_30.dll").is_file() else system / "SysWOW64" / "d3dx9_30.dll"
    d3dx = Path(explicit_d3dx or fallback_d3dx).expanduser().resolve()

    missing = [str(game / name) for name in (REFERENCE["executable"], *REQUIRED_DLLS)
               if not (game / name).is_file()]
    if not d3dx.is_file():
        missing.append(str(d3dx))
    sound_banks = sorted((game / "SOUND").rglob("*.abk"))
    if not sound_banks:
        missing.append(str(game / "SOUND" / "**" / "*.abk"))
    if not args.check_only:
        missing += [str(pcrecomp / file) for file in PCRECOMP_FILES if not (pcrecomp / file).is_file()]
    if missing:
        parser.error("Missing required offline inputs:\n  " + "\n  ".join(missing))
    exe = game / REFERENCE["executable"]
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    if digest != REFERENCE["sha256"]:
        parser.error(f"Unsupported NFSC.exe SHA-256: {digest}\nExpected {REFERENCE['sha256']} (Carbon 1.4)")
    # Verify DLL layouts against the hard-coded guest module mappings. Fail
    # before spending time cataloguing C if a binary is a different build.
    import struct
    layouts = {
        "d3dx9_30.dll": (d3dx, 0x00400000, 0x00260000),
        "msvcr71.dll": (game / "msvcr71.dll", 0x7c340000, 0x00056000),
        "msvcp71.dll": (game / "msvcp71.dll", 0x7c3a0000, 0x0007b000),
    }
    for name, (file, expected_base, expected_size) in layouts.items():
        with file.open("rb") as stream:
            header = stream.read(4096)
        if len(header) < 256 or header[:2] != b"MZ":
            parser.error(f"{name}: expected a PE32 DLL, but got an invalid DOS header")
        offset = struct.unpack_from("<I", header, 0x3c)[0]
        if offset + 24 + 60 > len(header) or header[offset:offset + 4] != bytes((0x50, 0x45, 0, 0)):
            parser.error(f"{name}: invalid PE header")
        opt = offset + 24
        machine = struct.unpack_from("<H", header, offset + 4)[0]
        magic = struct.unpack_from("<H", header, opt)[0]
        base = struct.unpack_from("<I", header, opt + 28)[0]
        size = struct.unpack_from("<I", header, opt + 56)[0]
        if machine != 0x14c or magic != 0x10b or (base, size) != (expected_base, expected_size):
            parser.error(f"{name}: unexpected PE32 layout: base={base:#x}, image size={size:#x}")
    print(f"Verified original game: {exe}\nVerified D3DX: {d3dx}\nVerified sound banks: {len(sound_banks)}", flush=True)
    if len(sound_banks) != 285:
        print("Warning: reference game has 285 .abk sound banks; check that SOUND is complete.", flush=True)
    if args.check_only:
        print("Offline game input check passed; no tools needed and no files generated.")
        return
    print(f"Verified pcrecomp: {pcrecomp}", flush=True)

    env = os.environ.copy()
    env["NFSC_GAME_ROOT"] = str(game)
    env["NFSC_D3DX_PATH"] = str(d3dx)
    env["PCRECOMP"] = str(pcrecomp)
    py = sys.executable
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    (ROOT / "src" / "recomp" / "gen_abk").mkdir(parents=True, exist_ok=True)
    analysis = work / "speed.analysis.exe"

    # The first catalog supplies function/code boundaries for the seed extractor.
    run(env, py, "scripts/analyze_binary.py", exe)
    run(env, py, "scripts/data_seeds.py", analysis, work / "seeds_data.json")
    run(env, py, "scripts/run_lift.py", "catalog", analysis,
        work / "seeds_data.json", work / "catalog_initial.json")
    run(env, py, "scripts/code_seeds.py", analysis, work / "catalog_initial.json",
        work / "seeds_code.json", "--merge", work / "seeds_data.json")
    run(env, py, "scripts/run_lift.py", "catalog", analysis,
        work / "seeds_code.json", work / "catalog.json")
    run(env, py, "scripts/run_lift.py", "lift", analysis,
        work / "catalog.json", ROOT / "src" / "recomp" / "gen")

    # Carbon's actual imports. EA LAN server and NFSCO are NOT required.
    run(env, py, "scripts/prepare_modules.py", "d3dx9_30.dll", *REQUIRED_DLLS)

    # Execute routines embedded in the stock EA sound banks.
    abk = ROOT / "src" / "recomp" / "gen_abk"
    abk_image = work / "abk_analysis.dll"
    abk_seeds = work / "abk_seeds.json"
    abk_catalog = work / "abk_catalog.json"
    run(env, py, "scripts/abk_module.py", game, abk_image, abk_seeds, abk / "abk_blocks.c")
    run(env, py, "scripts/run_lift.py", "catalog", abk_image, abk_seeds,
        abk_catalog, "--seeds-only")
    run(env, py, "scripts/run_lift.py", "lift", abk_image, abk_catalog,
        abk, "--prefix", "abk_")
    print("\nBase-game C generation completed. Build: cd android && ./gradlew assembleDebug", flush=True)
    print("NFSCO and server.dll are not needed for this single-player build.")


if __name__ == "__main__":
    main()
