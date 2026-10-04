$here = "C:\Users\james\i76-uncap-lab\src"
$vc = Get-ChildItem "C:\Program Files (x86)\Microsoft Visual Studio\2019\*\VC\Auxiliary\Build\vcvars32.bat" -EA SilentlyContinue | Select-Object -First 1
if (-not $vc) { "no vcvars32 found"; exit 1 }
$log = Join-Path $here 'build-u32x.log'
$out = Join-Path $here 'u32x_new.dll'
Remove-Item $out -Force -EA SilentlyContinue
# Redirect INSIDE cmd, not via PowerShell 2>&1 - that wraps stderr in a
# NativeCommandError and aborts even on a clean compile (music-fix/build.ps1).
$cmd = "call `"$($vc.FullName)`" && cd /d `"$here`" && cl /nologo /O2 /LD u32x.c /link /DEF:u32x.def user32.lib /OUT:`"$out`""
& cmd.exe /c "$cmd > `"$log`" 2>&1"
if (Test-Path $out) {
    $b = [IO.File]::ReadAllBytes($out)
    $pe = [BitConverter]::ToInt32($b, 0x3c); $mach = [BitConverter]::ToUInt16($b, $pe + 4)
    "BUILT $($b.Length) bytes  machine=0x{0:X}  $(if($mach -eq 0x14c){'x86 OK'}else{'WRONG ARCH'})" -f $mach
} else {
    "BUILD FAILED - tail of log:"
    Get-Content $log -Tail 12 | ForEach-Object { "   $_" }
}
