param([int]$Seconds=30,[switch]$TraceNative)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$game=(Resolve-Path (Join-Path $root '../Need for Speed Carbon 2005')).Path
$logPath=Join-Path $root 'work/windows-test'
New-Item -ItemType Directory -Force -Path $logPath | Out-Null
$args=@('--game-root',('"'+$game+'"'),'--log-dir',('"'+$logPath+'"'),'--windowed')
if($TraceNative){$args+='--trace-native'}
# Test only the statically lifted path, independently of inherited debug flags.
Remove-Item Env:NFSC_NATIVE,Env:NFSC_NATIVE_RANGE -ErrorAction SilentlyContinue
$process=Start-Process -FilePath "$root/build/NFSC-Recompiled.exe" -ArgumentList $args -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput "$logPath/stdout.txt" -RedirectStandardError "$logPath/stderr.txt" -PassThru
$deadline=[DateTime]::UtcNow.AddSeconds($Seconds)
while(!$process.HasExited -and [DateTime]::UtcNow -lt $deadline){Start-Sleep -Milliseconds 500;$process.Refresh()}
if(!$process.HasExited){
  $process.Kill($true)
  Write-Output "Test duration reached ($Seconds seconds); inspect frame and crash logs. This is not a pass result."
}else{Write-Output ('Windows host exit code: '+$process.ExitCode)}
Get-Content -LiteralPath "$logPath/stderr.txt" -Tail 30
