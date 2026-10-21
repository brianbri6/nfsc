param([int]$Jobs=6)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$vswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$visualStudio=(& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | Select-Object -First 1)
if(!$visualStudio){throw 'MSVC x86 tools not found'}
$cmake=Join-Path $visualStudio 'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
$ninja=Join-Path $visualStudio 'Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja/ninja.exe'
if(!(Test-Path -LiteralPath "$root/src/recomp/gen/lift_stats.json")){throw 'Finish the local lift before compiling'}
$reference=Get-Content -LiteralPath "$root/config/reference.json" -Raw | ConvertFrom-Json
$game=Join-Path $root $reference.source_directory
if((Get-FileHash -LiteralPath (Join-Path $game $reference.executable) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $reference.sha256){throw 'Game executable differs from the selected reference'}
$batch=@(
  '@echo off',
  "call `"$visualStudio/VC/Auxiliary/Build/vcvarsall.bat`" x86 >nul",
  'if errorlevel 1 exit /b 1',
  "`"$cmake`" -S `"$root`" -B `"$root/build`" -G Ninja -DCMAKE_MAKE_PROGRAM=`"$ninja`" -DCMAKE_C_COMPILER=cl -DCMAKE_BUILD_TYPE=Release",
  'if errorlevel 1 exit /b 1',
  "`"$cmake`" --build `"$root/build`" --parallel $Jobs",
  'exit /b %errorlevel%'
)
[IO.File]::WriteAllLines("$root/work/build-windows.cmd",$batch,[Text.Encoding]::ASCII)
$ErrorActionPreference='Continue'
& "$root/work/build-windows.cmd"
if($LASTEXITCODE -ne 0){throw 'Carbon Windows compilation failed; inspect the build log'}
