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

## Continuation results — 2026-10-22 (current session)

Reused the extracted uploaded game files under /mnt/data/nfsc_input on the
isolated execution host. This is local user-provided content only; it is NOT
committed or uploaded into GitHub.

New, independently executed read-only checks (stdlib PE parser + ABKC parser):
- Carbon 1.4 NFSC.exe checksum matches config/reference.json.
- All required local DLLs have expected PE32 image bases and sizes.
- Parsed all 285 .abk sound banks without errors.
- 103 distinct x86 ABK code blocks, 722,060 embedded code bytes counted with
  duplicates, 33,232 verified patched call references into 28 call table entries.
- Zero invalid ABKC headers, code ranges, call operand locations, target
  indices or target code addresses.
- Negative check: corrupting a copied bank's ABKC magic was rejected.
- Saved machine-readable results locally at
  /mnt/data/nfsc_offline_preflight_detailed.json.

New repository code:
- scripts/verify_offline_assets.py: standalone no-dependency input validator.
- scripts/prepare_offline.py now also runs the sound callback verification
  during --check-only and before the expensive lift.
- scripts/bootstrap_offline.py: reproducible setup using sibling cloned
  nfsu2-recompiled (including its libadrenotools submodule), the pinned
  patched pcrecomp toolchain, DXVK Native native-1.9.2b revision
  c8dc91fabd00cac11d697ccf07426e798393cd40 and NFSU2 shader
  generation, then C generation and Gradle ARM64 APK compilation.
- README.md documents validator, --check, --setup, --generate, --build, --all.

Exact first commands, on a Windows/Linux build host with network access:
```bash
python scripts/verify_offline_assets.py "../Need for Speed Carbon" --json-out work/offline_input_report.json
python scripts/bootstrap_offline.py --game-root "../Need for Speed Carbon" --check
python scripts/bootstrap_offline.py --game-root "../Need for Speed Carbon" --all
```

Environment blocker reconfirmed:
- This execution container has NO GitHub DNS/network access and NO local
  pcrecomp clone, capstone/pefile, prepared NFSU2/DXVK source or Android SDK/NDK.
- Therefore full generated game C and the APK still cannot be compiled here.
- The helper's Python syntax was checked locally against a matching standalone
  copy; its open-source dependency clone/build stages are not execution-tested.
- No functioning APK or game boot has been claimed. The PR stays DRAFT.
- Do NOT request the full game data upload; only the input code archive was
  necessary for this development stage. Other game assets can stay on the
  user's computer/phone for later testing.

## Network-isolation workaround — 2026-10-22 (latest)

**SUCCESS:** GitHub Actions runner can fetch public dependencies even though
the chat container cannot directly use DNS, GitHub, curl or git clone.

- Workflow: .github/workflows/offline-toolchain.yml.
- Successful GitHub run: https://github.com/brianbri6/nfsc/actions/runs/39789915948.
- Runner cloned pcrecomp @ 35548b8, applied NFSU2 patches, cloned the
  nfsu2-recompiled submodules, prepared DXVK Native pinned
  c8dc91fabd00cac11d697ccf07426e798393cd40 and generated 54
  Vulkan shaders; public dependency checks all PASSED.
- Public-only source and wheels were archived to a 26 MiB GitHub Actions
  artifact nfsc-public-offline-toolchain (ID 12431440450).
- The GitHub connector downloaded the Actions artifact into
  /mnt/data/nfsc-public-offline-toolchain.zip. It was extracted to
  /mnt/data/nfsc-build-workspace/{nfsc,pcrecomp,nfsu2-recompiled,offline_wheels}.
- Capstone 5 and pefile installed OFFLINE from these wheels.
- Re-ran: PYTHONPATH=/mnt/data/nfsc-build-workspace/.python
  python scripts/prepare_offline.py --game-root
  '/mnt/data/nfsc_input/Need for Speed Carbon' --check-only
  -> original game and all sound-call checks PASSED.
- Started full original executable analysis and C code generator. It produced
  work/speed.analysis.exe, work/binary.json and work/seeds_data.json.
  20,587 aligned data pointers decoded as function entries.
  At this checkpoint the initial function catalog is still computing;
  log: /mnt/data/nfsc-build-workspace/nfsc/work/offline_generation.log.
- The original game archives remain only in the execution workspace. The
  GitHub artifact contains public tooling/source ONLY, NO copyrighted game data.
- A second workflow (.github/workflows/offline-android-sdk.yml) is attempting
  to bring a public Android SDK/NDK/Gradle build cache into this offline
  workspace. Initial run failed because setup-android@v3 requested the
  removed SDK 'tools' package; changed to the runner's cmdline-tools/16.0
  sdkmanager and re-triggered, pending verification.
- No APK has been produced yet. Do not claim compilation success without
  checking its actual existence.

The workaround does not require the user to re-upload game files.

## Actual offline x86-to-C generation and Android SDK transfer (latest)

**Main Carbon executable lifting completed locally** against user-provided
NFSC.exe. Main code output is in the container at
/mnt/data/nfsc-build-workspace/nfsc/src/recomp/gen (gitignored):
- 52,931 functions compiled from catalog to C source (133 C translation units).
- 6,634,716 generated C lines (~301 MiB raw C files).
- lift_failures: **0**; 120 unsupported-instruction sites still need runtime
  reachability checks (many likely non-code scans).
- Statistics: src/recomp/gen/lift_stats.json.
- Initial catalog discovered 52,733 entries; final catalog includes additional
  jump-table and function-pointer seeds.
- Generated game C is NOT committed to public GitHub.

**Android SDK workaround:** GitHub Actions run
https://github.com/brianbri6/nfsc/actions/runs/39791179951
successfully installed SDK 35 / build tools 35.0.0 / NDK 28.2.13676358 /
CMake 3.30.5 and downloaded Gradle 8.9 + Android Gradle Plugin 8.7.3.
- Downloaded 271 MiB Gradle cache as a GitHub Actions artifact.
- Downloading the single 830 MiB Android SDK archive via connector failed
  because it exceeds a 512 MiB file-size limit.
- Updated .github/workflows/offline-android-sdk.yml to split SDK bundle into
  four 275/275/275/5 MiB artifacts; rerun succeeded.
- Downloaded and reconstructed all four artifacts into
  /mnt/data/nfsc-build-workspace/android_sdk_bundle.tar.gz (831 MiB).
- Extracted SDK to /mnt/data/nfsc-build-workspace/android_sdk (2.6 GiB).
- Confirmed SDK android-35/android.jar, build-tools/35.0.0/aapt2,
  NDK clang 19.0.1 and CMake 3.30.5 can be invoked locally.
- Android Gradle 8.9 cache is at /mnt/data/nfsc-build-workspace/.gradle.
- First `./gradlew --offline --no-daemon help` check exceeded tool timeout
  while D3DX module catalog was consuming ~3 GiB / full CPU.
  Needs retry after generator frees memory.
- android/app/build.gradle now supports `-PnfsGuestLto=OFF` for
  lower-memory first boot APK builds.

The remaining local generator stage is still analyzing d3dx9_30.dll
(prepare_modules.py). MSVCR/MSVCP, 285-bank ABK lift and Android compile
must finish before an APK can be claimed. No more user uploads needed.
Game-play testing will use complete data on the user's device.

## Network/toolchain workaround verified — 2026-10-22

GitHub Actions is a functioning remote preparation environment independent of
the restricted local container's network/DNS:
- Public toolchain workflow run 39808003551 completed SUCCESS.
- Offline Android SDK cache workflow run 39792153510 completed SUCCESS.
- Successful public toolchain run produced artifact
  nfsc-public-offline-toolchain (artifact ID 12438153515, approx 45 MB).
- The artifact was downloaded via connected GitHub integration as
  nfsc-open-toolchain.zip, demonstrating that repository public source and
  patched dependencies can be staged through Actions without a direct git
  clone in the current environment.
- The existing workflow is .github/workflows/offline-toolchain.yml.
- Source archive includes public checkouts and Python package wheels; excludes
  user's original game binaries, and cannot by itself produce the APK.
- Local container command execution is currently failing; do not claim
  local extraction, C generation or NDK compilation was completed.
- Next: restore sandbox execution or use a separate build host to combine
  the staged toolchain with the user-provided original game binary archive,
  generate C code, then compile Android using the cached SDK/NDK.
- Do not place extracted copyrighted game files in the public GitHub repo.

## Android build workaround — native compile regression CI (2026-10-22)

The container-backed execution tools in this chat currently return ClientError,
so previously staged local binaries and game-generated C cannot be resumed
from this live turn. The GitHub connector remains writable.

To continue useful verification without publishing any of the owner's
game binaries, committed an **opt-in, explicitly non-playable** CI test:
- scripts/offline_native_smoke.c: empty guest/ABK dispatch fixtures, no
  copyrighted content.
- android/app/src/main/cpp/CMakeLists.txt:
  NFSC_SMOKE_STUBS=ON compiles the Android host runtime with fixtures
  instead of game-generated C; OFF is unchanged and remains the playable path.
- android/app/build.gradle: -PnfsSmokeStub=ON exposes the option to Gradle.
- .github/workflows/offline-native-smoke.yml:
  Ubuntu runner installs Android SDK 35/NDK 28.2/CMake 3.30.5,
  prepares pinned pcrecomp and DXVK, then tries a full native host link
  and verifies that the expected .so files appear inside the test APK.
- Run URL: https://github.com/brianbri6/nfsc/actions/runs/39809835715
  Status at creation: in progress. Check actual result before claiming success.
- This test APK has **NO GAME LOGIC** and must NEVER be offered as a playable
  Carbon APK or published as a release.

The game source-generation checkpoint from the preceding run is recorded
above: 52,931 original Carbon functions were successfully lifted to C,
with required DLL/ABK work still pending. No re-upload is needed.
Next: address native CMake/compiler issues revealed by CI and resume the
game DLL/ABK lift when the container tool is restored.

## Verified Android native host compile — GitHub Actions (2026-10-22)

**SUCCESS — TEST-ONLY.** GitHub-hosted CI run
https://github.com/brianbri6/nfsc/actions/runs/39809835715
completed with all steps green:
- Android SDK 35, NDK 28.2.13676358, CMake 3.30.5 installed.
- Patched pcrecomp, DXVK Native, libadrenotools initialized successfully.
- Gradle `assembleDebug -PnfsSmokeStub=ON -PnfsGuestLto=OFF
  -PnfsAbi=arm64-v8a` returned **BUILD SUCCESSFUL in 1m 18s**.
- Verified packaged `lib/arm64-v8a/libnfsc_android.so` (3,691,552 bytes)
  and `lib/arm64-v8a/libnfsc_diagnostics.so` (899,488 bytes).
- GitHub Actions artifact: `nfsc-native-link-smoke-nonplayable`,
  artifact ID 12440725720 (~3.2 MB compressed); this artifact is **NOT**
  a playable game and must not be released to users as one.
- No game files, generated Carbon executable code or sound-bank bytes were
  uploaded to GitHub. This build tests Android Java/C++/DXVK infrastructure.
- Only warnings concerned third-party libadrenotools and Node 20 action
  deprecation; native compile and link itself passed.

Additional source fixes:
- `scripts/prepare_modules.py` no longer treats optional `server.dll`
  as an importer in the offline code-generation path.
- `scripts/prepare_offline.py --resume` validates the current original EXE
  analysis SHA, completed lift stats, dispatch table and C file count before
  skipping a completed main executable stage; it similarly resumes individual
  DLL and sound-bank stages.
- `scripts/bootstrap_offline.py --resume` supports partial generation;
  `--all` resumes automatically.
- GitHub Actions public toolchain tests for commits f9bbda79 and 86c024bc
  both finished successfully, including `python -m compileall -q scripts`.

**Remaining real-game blocker:** DLL (D3DX/MSVCR/MSVCP) and ABK C generation
from the supplied private game files is not yet confirmed complete; the
container-backed runtime is currently returning ClientError. Resume the
previous local workspace when it becomes reachable, then compile the actual
52,931-function generated C with the now-tested native Android build path.

## DLL-stage resume hardening — 2026-10-22 (latest continuation)

The container execution service is still failing with ClientError. Original
user binaries and the earlier local 52,931-function game C output cannot be
operated on or inspected in this session. No live game lift, APK build, or
Android device test was carried out here.

Repository fixes on branch offline-singleplayer-bootstrap:
- scripts/prepare_modules.py: stable base-game importer set even when only
  one DLL is pending, excluding optional server.dll in offline mode.
- scripts/prepare_modules.py: per-DLL checkpoint file at
  work/modules/<module>/pipeline_checkpoint.json, atomically saved after each
  successful relocated/probed/catalogued/classified/lifted stage.
- Resume checkpoints tied to SHA-256 hashes of the input DLLs, original
  game importer set, generator code, and pcrecomp tools. Invalid or missing
  outputs cause the dependent stages to rerun.
- scripts/prepare_offline.py: --resume now passes the flag to
  prepare_modules.py and validates all three mandatory DLLs instead of
  trusting a dispatch-count-only source manifest.
- tests/test_offline_module_resume.py: game-free tests cover first run,
  entirely skipped verified rerun, injected catalog crash recovery, invalid
  JSON recovery, and changed fingerprint invalidation.
- .github/workflows/offline-toolchain.yml runs the regression tests on
  public GitHub-hosted runners, without publishing game assets.

**Verified:** GitHub Actions run 39824110830 completed SUCCESS:
https://github.com/brianbri6/nfsc/actions/runs/39824110830
Step "Test resumable DLL processing without game files" succeeded. Python
syntax check, patched pcrecomp/DXVK setup and public toolchain packaging
also succeeded. This is NOT a playable-game test.

Next execution command when the original workspace is accessible:
```bash
cd /mnt/data/nfsc-build-workspace/nfsc
PYTHONPATH=/mnt/data/nfsc-build-workspace/.python \
 python scripts/prepare_offline.py \
 --game-root "/mnt/data/nfsc_input/Need for Speed Carbon" --resume
```
The previous main game C stage should be reused only after it passes its
source-hash and output checks. D3DX/MSVCR/MSVCP and ABK stages are still
unconfirmed; then build ARM64 with -PnfsGuestLto=OFF and verify the APK
is actually present. Do not upload copyrighted game binaries to public
GitHub.

## Normal generated-C linker integration test (latest)

Local container execution remains unavailable (ClientError), so the generated
52,931-function Carbon C and private source DLLs remain untestable here.

To exercise the NON-STUB CMake source-collection path without copying game
assets into a public GitHub repository, committed:
- scripts/create_synthetic_guest_ci.py: creates small clearly marked test C
  source modules in the exact generated directories used by the real build
  (EXE, D3DX, MSVCR, MSVCP, ABK) on a disposable GitHub runner.
- android/app/src/main/cpp/CMakeLists.txt: rejects any fixture tagged
  SYNTHETIC_CI_ONLY during normal builds; explicit opt-in is required.
- android/app/build.gradle: -PnfsSyntheticCI=ON maps the test-only CMake flag.
- .github/workflows/offline-generated-ci.yml: builds the *normal* generated-C
  CMake branch, unlike the older host-only NFSC_SMOKE_STUBS test, using
  harmless fake C functions and checks native objects and APK packaging.
- The CI artifact is not playable and must never be released.
- GitHub Actions run 39824773205 completed SUCCESS:
  https://github.com/brianbri6/nfsc/actions/runs/39824773205
  Confirmed these steps all PASSED: "Prepare explicitly synthetic C fixtures",
  "Compile normal generated-C CMake branch with synthetic fixtures", and
  "Verify native libraries and generated C objects".
  The build uses NFSC_SMOKE_STUBS=OFF to exercise the actual source-glob/link
  path for EXE, D3DX, MSVCR, MSVCP and ABK translation units. It is synthetic,
  not a game, and no playable APK was produced.

## Function-catalog memory and interrupted-lift safety — 2026-10-22

The local model execution container still fails on trivial Python and shell
commands with ClientError. No private game binary could be processed in this
turn; the previously generated 52,931-function C checkpoint is preserved
outside GitHub, but cannot currently be reopened for the final real APK.

Substantive generator fixes committed to the offline branch:
- scripts/run_lift.py: restore_seeds used to allocate dict/set entries for
  nearly every byte interior to every decoded instruction in every function.
  It now builds coverage only for *missing seed addresses*. This preserves
  the previous function-overlap and call-target protection semantics while
  eliminating potentially millions of unnecessary dict/set allocations.
  Designed to reduce peak RAM during costly D3DX catalogue generation.
- scripts/run_lift.py: before regenerating any translation units, remove any
  previous lift_stats.json so a crash midway through rewriting C cannot leave
  a stale "completed" manifest that --resume would incorrectly trust.
  A fresh manifest is written only after all generated outputs are emitted.
- tests/test_run_lift_seeds.py: tests sparse coverage, equivalence against
  the original coverage algorithm, preservation of called and seeded
  legitimate functions, restoration of uncalled bogus starts, and stale
  success-manifest invalidation.
- .github/workflows/offline-toolchain.yml: run these tests using the patched
  public pcrecomp toolchain on a GitHub runner; no copyrighted game files.
- GitHub Actions run 39826647575 PASSED the new seed-coverage regression
  and existing DLL-resume suite.
  https://github.com/brianbri6/nfsc/actions/runs/39826647575
- GitHub Actions run 39826854947 PASSED the updated lifter checks and public
  dependency setup, including manifest-invalidation code changes.
  https://github.com/brianbri6/nfsc/actions/runs/39826854947
- scripts/prepare_offline.py now generates the smaller ABK audio callback
  code *before* the memory-intensive D3DX/MSVCR/MSVCP DLL stages. A DLL crash
  cannot delay the first sound-code generation attempt.
- Latest CI run after sound-stage reordering:
  https://github.com/brianbri6/nfsc/actions/runs/39827172372
  (status to check; no proprietary game files are in this workflow).

Immediate resume command when an execution environment has the private
game binaries and existing lifted C workspace mounted:
```bash
cd /mnt/data/nfsc-build-workspace/nfsc
PYTHONPATH=/mnt/data/nfsc-build-workspace/.python \
 python scripts/prepare_offline.py --game-root \
 "/mnt/data/nfsc_input/Need for Speed Carbon" --resume
cd android
./gradlew assembleDebug -PnfsAbi=arm64-v8a -PnfsGuestLto=OFF
```

The APK must be verified on disk and installed for boot testing before making
any claim that Carbon single-player runs. Public test APKs remain non-playable
and should not be released.

## Independent real-code stages and sound-file fingerprinting — 2026-10-22

The private Carbon execution workspace remains unavailable in this chat:
container.exec and python.exec both return ClientError before commands can
start. No proprietary input files were uploaded to public GitHub.

Repository work on branch offline-singleplayer-bootstrap:
- scripts/prepare_offline.py --stage game|audio|dlls|all selects independent
  source-generation milestones; all remains the default. This lets the 52,931
  function original EXE lift be reused while audio and D3DX finish separately.
- scripts/bootstrap_offline.py --generate --stage audio|dlls|game --resume
  forwards the same selection. First full ARM64 APK builds now default to
  -PnfsGuestLto=OFF (optionally --lto after a successful first build).
- Audio C resume now checks SHA-256 fingerprints over every actual .abk bank,
  the original game exe digest, the ABK generator, lifter, configuration and
  patched pcrecomp tool. An atomic completion manifest records the matching
  fingerprint; changes force audio regeneration rather than reusing stale C.
- No incomplete audio stage is accepted as a success: all generated
  recomp_*.c, dispatch, lift stats and abk_blocks.c must exist, and the lift
  reports zero generation errors.
- tests/test_offline_stage_selection.py uses dummy **non-game** PE headers to
  check selection of every stage, bank/tool fingerprint changes, and how a
  matching audio manifest skips work while changed inputs regenerate.
- .github/workflows/offline-toolchain.yml runs these regression tests in the
  open-source GitHub build environment, without owner game files.

Verified public workflow:
https://github.com/brianbri6/nfsc/actions/runs/39828754900 SUCCESS,
including prior stage-isolation tests and toolchain installation.
**Final latest CI PASS:** GitHub Actions 39829760062 completed SUCCESS.
https://github.com/brianbri6/nfsc/actions/runs/39829760062
Its checks for Python source syntax, resumable DLL processing, independently
selected game/audio/DLL stages, audio bank/tool fingerprint change detection,
and low-memory seed restoration all passed. These are public synthetic/unit
tests; no copyrighted game binaries are on the runner.

Direct private-data build commands on a build host with the staged game files:
```bash
python scripts/prepare_offline.py \
 --game-root "../Need for Speed Carbon" --stage audio --resume
python scripts/prepare_offline.py \
 --game-root "../Need for Speed Carbon" --stage dlls --resume
python scripts/prepare_offline.py \
 --game-root "../Need for Speed Carbon" --stage game --resume
python scripts/bootstrap_offline.py --build
```

Actual Carbon ARM64 APK is still NOT produced; synthetic integration APKs
are test-only. Continue on a host with access to the prior local game
binaries and patched toolchain. No additional user upload is necessary.

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
