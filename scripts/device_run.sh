#!/usr/bin/env bash
# One device test cycle: install the debug APK, start the game directly
# (the launcher's defaults), wait, and print the runtime log after the
# guest DLLs are mapped.   scripts/device_run.sh [seconds] [--no-install]
set -u
export MSYS_NO_PATHCONV=1
root="$(cd "$(dirname "$0")/.." && pwd)"
seconds="${1:-25}"
pkg=com.nfscarbon.androidevolved
if [ "${2:-}" != "--no-install" ]; then
    adb install -r "$(cygpath -w "$root/android/app/build/outputs/apk/debug/app-debug.apk")" | tail -1
fi
adb shell am force-stop $pkg
adb logcat -c
adb shell am start -n $pkg/.GameActivity --es language Spanish --ez widescreen true >/dev/null
sleep "$seconds"
mkdir -p "$root/work/device"
adb logcat -d -v time > "$root/work/device/last.log"
grep -aE "/NFS[A-Z ]*\(|F DEBUG|F libc" "$root/work/device/last.log" \
  | grep -avE "Presented frames|Data directory|DirectInput kind|Keyboard |Created guest thread|Terminating guest|selfcheck|WaitForMultiple|D3D9 COM kind|Guest import " \
  | sed -n '/mapped at 00f60000/,$p' | cut -c1-300 | tail -45
