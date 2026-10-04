$here = "C:\Users\james\i76-uncap-lab\src"
$vc = Get-ChildItem "C:\Program Files (x86)\Microsoft Visual Studio\2019\*\VC\Auxiliary\Build\vcvars32.bat" -EA SilentlyContinue | Select-Object -First 1
$log = Join-Path $here 'build-u32x-log.log'
$out = Join-Path $here 'u32x_newlog.dll'
Remove-Item $out -Force -EA SilentlyContinue
$cmd = "call `"$($vc.FullName)`" && cd /d `"$here`" && cl /nologo /O2 /LD /DU32X_LOG u32x.c /link /DEF:u32x-log.def user32.lib /OUT:`"$out`""
& cmd.exe /c "$cmd > `"$log`" 2>&1"
if (Test-Path $out) { "BUILT LOG VARIANT $((Get-Item $out).Length) bytes" }
else { "FAILED:"; Get-Content $log -Tail 10 | ForEach-Object { "   $_" } }
