#!/usr/bin/env python3
"""Reproducible offline Carbon ARM64 setup/build helper (no game files uploaded).

From the NFSC repository root:
  python scripts/bootstrap_offline.py --game-root "../Need for Speed Carbon" --check
  python scripts/bootstrap_offline.py --game-root "../Need for Speed Carbon" --all

--all prepares sibling open-source dependencies, generates local C and builds
an Android debug APK. Requires Git, Python/pip, Android SDK/NDK, CMake, JDK,
Vulkan SDK's glslangValidator and spirv-val, and an internet-enabled host.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT.parent
GAME_DEFAULT = WORKSPACE / "Need for Speed Carbon"
PCRECOMP_COMMIT = "35548b8"
DXVK_COMMIT = "c8dc91fabd00cac11d697ccf07426e798393cd40"


def run(args, cwd=ROOT):
    print("+", " ".join(str(x) for x in args), flush=True)
    subprocess.run([str(x) for x in args], cwd=cwd, check=True)


def output(args, cwd=ROOT):
    return subprocess.check_output([str(x) for x in args], cwd=cwd, text=True).strip()


def require_program(name):
    if not shutil.which(name):
        raise RuntimeError(f"Missing {name}. Install it and add it to PATH.")


def install_git_source(target, url, *options):
    if (target / ".git").exists():
        print(f"Using existing checkout: {target}", flush=True)
        return False
    if target.exists():
        raise RuntimeError(f"Cannot clone into occupied non-git path: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", *options, url, target], cwd=WORKSPACE)
    return True


def setup_sources():
    require_program("git")
    nfsu2 = WORKSPACE / "nfsu2-recompiled"
    install_git_source(nfsu2, "https://github.com/codepdbh/nfsu2-recompiled.git",
                       "--recurse-submodules")
    run(["git", "submodule", "update", "--init", "--recursive"], cwd=nfsu2)
    if not (nfsu2 / "third_party/libadrenotools/CMakeLists.txt").is_file():
        raise RuntimeError("The libadrenotools submodule was not initialized.")

    pcrecomp = WORKSPACE / "pcrecomp"
    fresh = install_git_source(pcrecomp, "https://github.com/sp00nznet/pcrecomp.git")
    if fresh:
        run(["git", "checkout", PCRECOMP_COMMIT], cwd=pcrecomp)
        patches = sorted((nfsu2 / "patches/pcrecomp").glob("*.patch"))
        if not patches:
            raise RuntimeError("The NFSU2 pcrecomp patch series is missing.")
        run(["git", "am", *patches], cwd=pcrecomp)
    elif not (pcrecomp / "runtime/recomp32/recomp_types.h").is_file():
        raise RuntimeError("Existing pcrecomp checkout is incomplete.")
    print("Using pcrecomp:", output(["git", "rev-parse", "--short", "HEAD"], cwd=pcrecomp))

    native = WORKSPACE / "reference/dxvk-native"
    install_git_source(native, "https://github.com/Joshua-Ashton/dxvk-native.git",
                       "--branch", "native-1.9.2b")
    revision = output(["git", "rev-parse", "HEAD"], cwd=native)
    if revision != DXVK_COMMIT:
        raise RuntimeError(f"DXVK Native revision differs from pinned {DXVK_COMMIT}: {revision}")
    dxvk = nfsu2 / "build/dxvk-source"
    if not (dxvk / "src/d3d9").exists():
        run([sys.executable, "ports/dxvk_android/prepare.py", native, dxvk], cwd=nfsu2)
    built = list((dxvk / "generated").glob("*.spv")) if (dxvk / "generated").is_dir() else []
    if len(built) < 54:
        require_program("glslangValidator")
        require_program("spirv-val")
        run([sys.executable, "ports/dxvk_android/shaders.py", dxvk], cwd=nfsu2)
    print(f"Prepared DXVK and {len(list((dxvk / 'generated').glob('*.spv')))} built-in shaders.")
    run([sys.executable, "-m", "pip", "install", "capstone", "pefile"])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--game-root", type=Path, default=GAME_DEFAULT)
    p.add_argument("--abi", choices=["arm64-v8a", "armeabi-v7a"], default="arm64-v8a")
    p.add_argument("--check", action="store_true", help="Only check supplied game inputs, no network")
    p.add_argument("--setup", action="store_true", help="Clone and prepare open-source toolchain")
    p.add_argument("--generate", action="store_true", help="Regenerate original game C sources")
    p.add_argument("--build", action="store_true", help="Compile Android debug APK from generated C")
    p.add_argument("--all", action="store_true", help="Preflight + setup + generate + build")
    p.add_argument("--resume", action="store_true", help="Reuse verified completed recompilation stages")
    p.add_argument("--stage", choices=("all", "game", "audio", "dlls"), default="all",
                   help="Select one code-generation stage when using --generate")
    p.add_argument("--lto", action="store_true",
                   help="Enable memory-intensive ThinLTO (off for first real APK build)")
    args = p.parse_args()
    if not (args.check or args.setup or args.generate or args.build or args.all):
        p.error("Select --check, --setup, --generate, --build, or --all")
    try:
        game = args.game_root.expanduser().resolve()
        if args.check or args.all or args.generate:
            run([sys.executable, ROOT / "scripts/prepare_offline.py",
                 "--game-root", game, "--check-only"])
        if args.setup or args.all:
            setup_sources()
        if args.all and args.stage != "all":
            p.error("--all builds an APK and therefore requires --stage all")
        if args.generate or args.all:
            command = [sys.executable, ROOT / "scripts/prepare_offline.py",
                       "--game-root", game, "--stage", args.stage]
            if args.resume or args.all:
                command.append("--resume")
            run(command)
        if args.build or args.all:
            if not (os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or
                    (ROOT / "android/local.properties").is_file()):
                raise RuntimeError("Android SDK path missing: set ANDROID_HOME or create android/local.properties")
            if os.name == "nt":
                run(["cmd", "/c", "gradlew.bat", "assembleDebug", f"-PnfsAbi={args.abi}",
                     f"-PnfsGuestLto={'ON' if args.lto else 'OFF'}"],
                    cwd=ROOT / "android")
            else:
                run(["bash", "./gradlew", "assembleDebug", f"-PnfsAbi={args.abi}",
                     f"-PnfsGuestLto={'ON' if args.lto else 'OFF'}"],
                    cwd=ROOT / "android")
            apk = ROOT / "android/app/build/outputs/apk/debug/app-debug.apk"
            if not apk.is_file():
                raise RuntimeError(f"Gradle exited successfully but APK was not found: {apk}")
            print(f"APK created: {apk} ({apk.stat().st_size:,} bytes)")
    except (OSError, subprocess.CalledProcessError, RuntimeError) as e:
        p.exit(1, f"Offline build stopped: {e}\n")


if __name__ == "__main__":
    main()
