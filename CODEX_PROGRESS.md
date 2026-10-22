# CODEX_PROGRESS — NFSC stock single-player Android bring-up

Updated: 2026-10-22

## Goal
Build and boot original PC Need for Speed Carbon 1.4 on Android without requiring
NFSCO or the EA LAN server. First milestone: main menu, then sound / input,
then an offline race. Preserve NFSCO source for a later phase.

## Working / source already present
- Existing Android launcher, Direct3D9-to-Vulkan DXVK path, input and audio runtime.
- Base game's analysis, disassembly and lifted-C code generators.
- Native Android CMake/Gradle structure with selectable ABIs.
- Existing EA sound-bank code generator and DLL relocation/lifting.
- Actual gameplay is NOT VERIFIED, and no new APK was compiled in this change.

## Files changed on branch offline-singleplayer-bootstrap
- android/app/src/main/cpp/CMakeLists.txt: NFSCO and LAN generated modules opt-in.
- android/app/src/main/cpp/guest_runtime.cpp: guard NFSCO dispatch and OnAttach.
- android/app/src/main/cpp/guest_modules.inc: omit palmont/logging guest modules by default.
- android/app/src/main/java/com/nfscarbon/androidevolved/LauncherActivity.java:
  hide online-only server settings in the offline milestone.
- scripts/prepare_modules.py: accept NFSC_D3DX_PATH for a local DirectX DLL.
- scripts/prepare_offline.py (new): input/hash preflight and stock-game pipeline.
- README.md: correct game-file and recompiler setup instructions.
- CODEX_PROGRESS.md (this document).

## Required local inputs
- Original, unmodified NFSC.exe matching config/reference.json SHA-256.
- msvcr71.dll and msvcp71.dll from the matching game.
- SOUND/**/*.abk and the remaining PC game content for on-device tests.
- A 32-bit d3dx9_30.dll matching the expected runtime layout.
- Sibling patched pcrecomp checkout (sp00nznet/pcrecomp @ 35548b8 plus
  codepdbh/nfsu2-recompiled/patches/pcrecomp).
- Sibling nfsu2-recompiled checkout with prepared DXVK and libadrenotools.
- Android SDK 35, NDK 28.2.13676358, CMake 3.30.5, JDK.

## Changes and testing
- Inspected the original native CMake dependencies, guest dispatch registry,
  guest module registry, and boot path before modifying.
- Confirmed that original boot previously called startNfsco unconditionally.
- Reviewed the modified source via GitHub after commits. NFSCO-generated symbols
  are now behind the same optional build definition as the CMake module list.
- No original game binary, generated C modules, or prepared Android toolchain
  is available to this chat, so compilation and on-device execution are
  UNTESTED. Do not claim the APK is working or release-ready.
- Local container cannot resolve GitHub to clone the repo; changes made through
  the connected GitHub repository API on an isolated branch.

## Commands (run from nfsc repository root)

```bash
python -m pip install capstone pefile
python scripts/prepare_offline.py --game-root "../Need for Speed Carbon" --check-only
python scripts/prepare_offline.py --game-root "../Need for Speed Carbon"
cd android
./gradlew assembleDebug
```

APK output after successful build: android/app/build/outputs/apk/debug/app-debug.apk.
Default target arm64-v8a; optional -PnfsAbi=armeabi-v7a.
Do not run scripts/prepare_nfsco.py or tools/nfsco_capture.c for offline mode.

## Known blockers / risks
- The game binary has now been provided and hash-verified. Source lifting still awaits the patched pcrecomp/DXVK/SDK toolchains.
- The NFSU2 sibling prepared DXVK toolchain is not checked in this repo.
- Game boot/race/audio behavior can only be determined through APK plus on-device
  logcat and actual game assets.
- The hash/layout check intentionally rejects other Carbon builds.
- The offline launcher still contains dormant online handlers; they are not
  exposed in the default UI.

## Input archive verification (2026-10-22)
User supplied ai.part1.rar (500 MiB) and ai.part2.rar (324 MiB).
Archive RAR5 multi-volume extraction completed locally into a sandbox-only
Need for Speed Carbon input directory; no game binaries were run.
- 577 files, 1,075,943,461 extracted bytes.
- NFSC.exe SHA-256: baaaaec33873d4ba7e4dbae6a5212049ffdcf9679a35d865d7625b4189952fd3
  EXACT match for config/reference.json.
- d3dx9_30.dll: ImageBase 0x00400000, SizeOfImage 0x00260000.
- msvcr71.dll: ImageBase 0x7c340000, SizeOfImage 0x00056000.
- msvcp71.dll: ImageBase 0x7c3a0000, SizeOfImage 0x0007b000.
- server.dll also present but no longer required for offline build.
- 285 .abk banks in SOUND, matching the generator's stated Carbon bank count.
- These are enough ORIGINAL GAME INPUTS for stock code generation. No NFSCO
  patch capture or related binary is necessary.
- This upload is NOT the full playable game: CARS, TRACKS, GLOBAL, FRONTEND,
  LANGUAGES and MOVIES directories are absent. Request remaining game data
  later for device testing.
- The execution sandbox has no Android SDK/NDK, pcrecomp checkout,
  nfsu2-recompiled/DXVK checkout, Python capstone/pefile, or network DNS to
  install them. Therefore source lifting and APK compilation could not be run.
- scripts/prepare_offline.py was updated to prefer the uploaded d3dx9_30.dll
  beside NFSC.exe, permit --check-only without pcrecomp installed, and
  verify PE32 image bases/sizes before cataloguing.

## Next steps
1. Game and sound binary inputs are verified; fetch pcrecomp + nfsu2-recompiled and run offline --check-only on the build host.
2. Run prepare_offline.py to generate lifted C and required DLL/sound modules.
3. Build ARM64 APK. Fix compiler/linker errors and record exact changes.
4. Install APK and put user-owned game data at /sdcard/nfsc/.
5. Boot to game menu, collect logcat at first failure, fix and retest.
6. Test race loading, controls, audio and graphics; enable NFSCO only after
   single-player proves stable.

## Resume prompt
Continue the offline Carbon Android single-player bring-up from
branch offline-singleplayer-bootstrap in brianbri6/nfsc. Preserve NFSCO
source for later. Inspect current git diff and CODEX_PROGRESS.md, validate
the patched pcrecomp and game hash, generate source with prepare_offline.py,
run the ARM64 Gradle build, fix errors, and test the earliest boot path first.
Do not report APK success without an actual build artifact.
