# NFS Carbon PC — Android Evolved

Static recompilation of the **PC version** of *Need for Speed: Carbon* (2006, `NFSC.exe` 1.4, x86) to native Android ARM64 and ARMv7. Fourth game of the *NFS Android Evolved* family, after [Underground 2](https://github.com/codepdbh/nfsu2-recompiled), [Underground 1](https://github.com/codepdbh/nfsu1-recompiled) and [Most Wanted](https://github.com/codepdbh/nfsmwpc-recompiled), whose runtime this port starts from.

It is **not** an emulator: every function of the original PC executable is translated ahead of time from x86 to C with [pcrecomp](https://github.com/sp00nznet/pcrecomp) (modified) and compiled with the Android NDK.

> **Status: early development, not playable yet.** The original executable's C lift was completed (52,931 functions); required DLL and sound-bank generation is still being finalized. Android native compilation with test fixtures has passed, but no playable APK exists.

No game files are included. You need your own copy of the PC game. Generated C code, analysis copies and logs are produced locally and never committed.

## Build on Windows with Android Studio

To build the **real offline game**, check out the
[`offline-singleplayer-bootstrap` branch](https://github.com/brianbri6/nfsc/tree/offline-singleplayer-bootstrap)
and extract your original verified Carbon files locally. Keep sibling folders
`nfsc/` and `Need for Speed Carbon/` in one workspace. Install Python 3.11+
(x64), Git for Windows, LunarG Vulkan SDK command line shader utilities
(`glslangValidator` and `spirv-val` in PATH), and in Android Studio install
SDK Platform 35, Android NDK 28.2.13676358, and CMake 3.30.5.

From PowerShell in the `nfsc` repository directory:

```powershell
py -3 scripts\bootstrap_offline.py --check
py -3 scripts\bootstrap_offline.py --setup
py -3 scripts\bootstrap_offline.py --generate --stage audio --resume
py -3 scripts\bootstrap_offline.py --generate --stage dlls --resume
py -3 scripts\bootstrap_offline.py --generate --stage game --resume
```

**Important:** the prior 52,931-function game C lift exists only in the
earlier execution workspace, not in the public GitHub repository. On a
fresh Windows checkout, the `--stage game` command must generate the
original game C from the local `NFSC.exe`. The game DLL and audio outputs
are also generated on the user's computer, not supplied by Android Studio.

Open **`nfsc/android`**, not the workspace root, as the Android Studio
project. Select Build > Build Bundle(s) / APK(s) > Build APK(s), or use the
Android Studio terminal:

```powershell
cd android
.\gradlew.bat assembleDebug -PnfsAbi=arm64-v8a -PnfsGuestLto=OFF
```

The APK, **if compilation succeeds**, is
`android/app/build/outputs/apk/debug/app-debug.apk`.
Real generated C is required: never turn on `nfsSmokeStub` or
`nfsSyntheticCI` for this APK. ThinLTO defaults to OFF for Android
Studio GUI builds to reduce peak memory until the first real APK links.
Please preserve the exact first error and console log if an operation fails;
do not copy game files into the public GitHub repository.

### Resume independent generated-code stages

On a machine with the original verified PC files and the patched pcrecomp
toolchain, each stage can now finish independently instead of rebuilding the
game after a D3DX crash:

```bash
# Preserve completed original NFSC.exe lift; finish audio callbacks first:
python scripts/prepare_offline.py --game-root "../Need for Speed Carbon" --stage audio --resume

# Finish just the required stock runtime DLLs, checkpointing each sub-stage:
python scripts/prepare_offline.py --game-root "../Need for Speed Carbon" --stage dlls --resume

# Recheck/reuse the 52,931-function main Carbon lift:
python scripts/prepare_offline.py --game-root "../Need for Speed Carbon" --stage game --resume

# Only once all three have succeeded:
python scripts/bootstrap_offline.py --game-root "../Need for Speed Carbon" --build
```

The bootstrap helper also supports `--generate --stage audio|dlls|game --resume`.
For first-boot APKs, ThinLTO is off by default to reduce the linker memory
footprint; use `--lto` after an actual game build has succeeded.

**Note:** These stages operate on the original copyrighted files stored only
on your local build machine, not the public GitHub Actions runners. Actions
tests the open-source toolchain and separate synthetic fixtures only.

## Verified game inputs and offline build helper

The user's two-part Carbon archive (ai.part1.rar / ai.part2.rar) contains
**exactly the NFSC.exe 1.4 hash needed** for this project's translated code,
the required D3DX/MSVCR/MSVCP DLLs and all **285 ABKC sound banks**.
The standard-library-only input verifier also checked **33,232** embedded x86
sound-bank call references against the original executable's call table;
there were **zero invalid targets**. These files remain local and are **not
uploaded to GitHub**.

Preflight and save a machine-readable report without pcrecomp, the NDK or any
third-party Python dependency:

```bash
python scripts/verify_offline_assets.py "../Need for Speed Carbon" --json-out work/offline_input_report.json
python scripts/bootstrap_offline.py --game-root "../Need for Speed Carbon" --check
```

To prepare pinned open-source dependencies, generate all C locally and attempt
the ARM64 APK (requires an internet-enabled host, Android Studio SDK 35,
NDK 28.2.13676358, CMake 3.30.5, Git, Java and the Vulkan shader tools
`glslangValidator` and `spirv-val`):

```bash
python scripts/bootstrap_offline.py --game-root "../Need for Speed Carbon" --all
```

You can run each stage separately using `--setup`, `--generate`, and `--build`. Add `--resume` with `--generate` to reuse finished code-generation stages; `--all` automatically uses verified resume mode. A main game lift is reused only when its analysis manifest matches the exact stock executable SHA-256, dispatch output and C file count.
The helper initializes NFSU2's libadrenotools submodule, pins the pcrecomp
patch base, checks DXVK Native's exact revision, prepares the Android DXVK
source and 54 shader binaries, and invokes `gradlew assembleDebug`. Existing
local tool checkouts are preserved.

### Android host-only link smoke test (not playable)

The workflow [offline-native-smoke.yml](.github/workflows/offline-native-smoke.yml)
compiles the Java launcher, Android host runtime, and DXVK native bridge with
empty CI-only guest dispatch symbols. The public test intentionally omits all
original Carbon executable, sound-bank and runtime-DLL code and **cannot play
the game**. Do not publish, install for gameplay, or label this test APK as
the actual Carbon port. The normal `assembleDebug` / `--all` path uses real
generated game C; these CI placeholder symbols are enabled *only* with
`-PnfsSmokeStub=ON` (or `-DNFSC_SMOKE_STUBS=ON` in CMake).

**Status:** Input validation, the main game's C lift and Android host
compilation with test fixtures have been verified. The actual combined
Carbon C + DLL + sound-bank APK has NOT been compiled or play-tested.
The remaining full game resource folders can be copied directly to the
phone; they do not need to be uploaded to this repository or chat.

### Full generated-C integration test (also not playable)

The separate workflow [offline-generated-ci.yml](.github/workflows/offline-generated-ci.yml)
compiles all five module categories (EXE, D3DX, MSVCR, MSVCP and ABK)
through the **normal** CMake generated-source path using synthetic,
copyright-free C fixtures. It checks C-object compilation and native
Android linking independently of the host-only smoke mode.

The fixtures are deliberately labeled `SYNTHETIC_CI_ONLY`; normal builds
fail if this marker is present. This workflow tests the build wiring,
**not Carbon gameplay**. It does not produce a releasable game.

## Offline single-player first (current build goal)

**The default Android APK is now configured for the original Carbon game, with no NFSCO dependency.** Online multiplayer and the EA LAN server are postponed. Gameplay has **not** been verified on a device yet.

This build requires the owner's original **NFSC.exe 1.4** whose SHA-256 is specified in `config/reference.json`, plus `msvcr71.dll`, `msvcp71.dll`, `SOUND/**/*.abk`, and a 32-bit `d3dx9_30.dll` from the DirectX 9 runtime. `server.dll`, `palmont.dll`, `logging.dll`, NFSCO captures and the NFSCO game folder are **not required** for this milestone.

Checkouts should be siblings:

```text
workspace/
  nfsc/
  pcrecomp/           # patched build below
  nfsu2-recompiled/   # prepared Android DXVK / libadrenotools dependencies
  Need for Speed Carbon/
    NFSC.exe
    msvcr71.dll
    msvcp71.dll
    SOUND/
    LANGUAGES/
    ...
```

Get the compatible recompiler from [sp00nznet/pcrecomp](https://github.com/sp00nznet/pcrecomp) and apply the [nfsu2-recompiled patches](https://github.com/codepdbh/nfsu2-recompiled/tree/main/patches/pcrecomp):

```bash
git clone https://github.com/codepdbh/nfsu2-recompiled.git ../nfsu2-recompiled
git clone https://github.com/sp00nznet/pcrecomp.git ../pcrecomp
cd ../pcrecomp
git checkout 35548b8
git am ../nfsu2-recompiled/patches/pcrecomp/*.patch
cd ../nfsc
python -m pip install capstone pefile
```

Prepare the locally generated C code from the **unmodified stock** executable:

```bash
python scripts/prepare_offline.py --game-root "../Need for Speed Carbon" --check-only
python scripts/prepare_offline.py --game-root "../Need for Speed Carbon"
cd android
./gradlew assembleDebug
```

The generator now auto-detects `d3dx9_30.dll` beside `NFSC.exe`, or uses the 32-bit copy in Windows `SysWOW64`. Supply `--d3dx /path/to/d3dx9_30.dll` if it is elsewhere. `--check-only` verifies just the game inputs, including the exact executable checksum and DLL layouts, before pcrecomp is installed. The code generator is platform-independent, but capturing NFSCO hooks (not part of the offline build) is Windows-specific. Prepare DXVK through the sibling NFSU2 Android build prerequisites. The Android project uses SDK 35, NDK 28.2.13676358 and CMake 3.30.5. The default ABI is arm64-v8a.

The debug APK, if compilation succeeds, appears at `android/app/build/outputs/apk/debug/app-debug.apk`. Copy your own original game assets into `/sdcard/nfsc/` on the device. An APK without the user's game files is not a complete playable game.

To intentionally build the separate NFSCO port **later**, generate its hook capture and C modules and pass `-DNFSC_ENABLE_NFSCO=ON` to CMake. `-DNFSC_ENABLE_LAN_SERVER=ON` similarly enables the optional generated `server.dll` module. Neither is selected by default. Do not mix an NFSCO-patched game's generated C with the offline build: the stock and NFSCO hook layouts are different.

### What is translated

| Code | Origin | Guest base |
|---|---|---|
| `NFSC.exe` 1.4 (SHA-256 `baaaaec3…2fd3`) | your copy | `0x00400000` |
| `d3dx9_30.dll` | your local DirectX runtime (`Windows/SysWOW64`) | `0x00D00000` |
| `msvcr71.dll`, `msvcp71.dll` | your game folder (Carbon links the VC++ 7.1 runtime dynamically) | `0x00F60000`, `0x00FC0000` |
| `server.dll` (LAN server) | your game folder | `0x01270000` |
| x86 routines inside `SOUND/**/*.abk` | your game folder | matched by content |

### Online: NFSCO

The plan includes the community online mod **NFSCO** ([nfsco.club](https://nfsco.club)). Its authors allowed translating their binaries for this Android port; their source code is not shared and is not needed. `tools/nfsco_capture.c` records, on Windows, the patches NFSCO's `palmont.dll` applies to the game at fixed guest addresses (palmont at `0x01060000`, its trampolines at `0x01200000`); see [docs/BINARY_REPORT.md](docs/BINARY_REPORT.md).

### Game language

Carbon picks its language from the registry value `Language`. The launcher writes it: Spanish (Spain), Spanish (Mexico), English and the other languages whose `LANGUAGES/<language>_Global.bin` is in your copy.

### Building

Use the **offline single-player instructions above** for the default APK. The scripts in `scripts/prepare_offline.py` regenerate the stock Carbon C code, its required MSVCR/MSVCP and D3DX modules, and the EA sound-bank routines, without needing NFSCO.

The NFSCO online path is preserved in `scripts/prepare_nfsco.py` and `tools/nfsco_capture.c` for a later milestone. The default offline APK never calls `OnAttach`.

### License and credits

Code in this repository: see each file. pcrecomp by sp00nznet. NFSCO by its authors (nfsco.club), translated with their permission. *Need for Speed* is a trademark of Electronic Arts; this project is not affiliated with EA.

---

## Español

Recompilación estática de la **versión de PC** de *Need for Speed: Carbon* (2006, `NFSC.exe` 1.4, x86) a Android ARM64 y ARMv7. Cuarto juego de la familia *NFS Android Evolved*, después de Underground 2, Underground 1 y Most Wanted, de cuyo runtime parte.

> **Estado: desarrollo inicial, todavía no jugable.** Ya están traducidos el código del juego, sus DLL de runtime y las rutinas de los bancos de sonido; la app de Android está en arranque.

No se incluyen archivos del juego: necesitas tu propia copia de PC. El código C generado, las copias de análisis y los registros se producen localmente y nunca se suben.

**Online:** se incluirá el mod comunitario **NFSCO** ([nfsco.club](https://nfsco.club)), cuyos autores han autorizado traducir sus binarios para este port.

**Idioma:** el launcher escribe el valor de registro `Language` que lee Carbon. Ofrece Español (España), Español (México), Inglés y los demás idiomas presentes en tu copia.
