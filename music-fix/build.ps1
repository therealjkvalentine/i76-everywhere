<#
  Build the base-game in-mission music fix: a proxy Strlkup.dll that IAT-hooks
  the game's cdaudio MCI calls and plays GOG's music\N.mp3 instead. See README.md.

  Needs a 32-bit GCC (w64devkit). A prebuilt Strlkup.dll is committed beside this
  script, so building is only necessary if you change strlkproxy.c.

  Usage:  ./build.ps1 [-Gcc "C:\Games\_tools\w64devkit\bin\gcc.exe"]
#>
param([string]$Gcc = "C:\Games\_tools\w64devkit\bin\gcc.exe", [switch]$Install,
      # Where to install. Falls back to the running game, then $env:I76_GAME_DIR,
      # then the usual locations - so this script is not tied to one machine's paths.
      [string]$GameDir)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$out  = Join-Path $here 'Strlkup.dll'
# Build to a SCRATCH path and only replace Strlkup.dll once the result is verified.
# Building straight over it destroyed the committed, known-good, currently-deployed
# binary on two consecutive failures - a build script must never be able to leave you
# worse off than before you ran it.
$tmp  = Join-Path $here 'Strlkup.build.dll'

# All winmm entry points are resolved at runtime via GetProcAddress, so no -lwinmm.
if (Test-Path $Gcc) {
    & $Gcc -m32 -O2 -s -shared -o $tmp (Join-Path $here 'strlkproxy.c') (Join-Path $here 'strlkup.def')
    if ($LASTEXITCODE) { throw "gcc build failed ($LASTEXITCODE)" }
} else {
    # MSVC fallback. w64devkit is not installed here, but Visual Studio 2019 Build
    # Tools are, with an x86 cross-compiler - `cl.exe` simply is not on PATH, which
    # is not the same as absent (an assumption that cost a round elsewhere in this
    # repo). vcvars32.bat sets up the x86 environment.
    Write-Host "gcc not at $Gcc - using MSVC x86 instead." -ForegroundColor DarkGray
    $vcvars = $null
    foreach ($root in @("${env:ProgramFiles}\Microsoft Visual Studio", "${env:ProgramFiles(x86)}\Microsoft Visual Studio")) {
        if (-not (Test-Path $root)) { continue }
        $f = Get-ChildItem $root -Recurse -Filter 'vcvars32.bat' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($f) { $vcvars = $f.FullName; break }
    }
    if (-not $vcvars) {
        Write-Host "Neither 32-bit gcc nor MSVC x86 found. Install w64devkit or VS C++ tools." -ForegroundColor Red
        exit 1
    }
    $log = Join-Path $here 'build.log'
    if (Test-Path $tmp) { Remove-Item $tmp -Force }

    # MSVC does NOT honour .def forwarder syntax. `name = otherdll.name` in a .def
    # is read by link.exe as an alias to a LOCAL symbol, so it reports five
    # unresolved externals (StrLookupCreate and friends) - which is right, they do
    # not exist here; they live in strlkup_orig.dll. The MSVC way to build a
    # forwarder is /EXPORT: with a DOTTED target, which link.exe recognises as
    # "forward to that DLL". gcc/dlltool reads the .def correctly, so the .def stays
    # for that path.
    $fwd = @('StrLookupCreate','StrLookupDestroy','StrLookupFind','StrLookupFormat') |
           ForEach-Object { "/EXPORT:$_=strlkup_orig.$_" }
    # DATA, not a function: exported as a variable, so the comma-DATA suffix.
    $fwd += "/EXPORT:StrLookup_Global_Object=strlkup_orig.StrLookup_Global_Object,DATA"

    # Redirection inside cmd, NOT `2>&1` in PowerShell: that wraps stderr in a
    # NativeCommandError and aborts under $ErrorActionPreference='Stop' even on a
    # successful compile (vcvars emits a benign vswhere warning).
    $cmd = "call `"$vcvars`" && cd /d `"$here`" && " +
           "cl /nologo /LD /MT /O2 /W3 /D_CRT_SECURE_NO_WARNINGS strlkproxy.c " +
           "/Fe:`"$tmp`" /link user32.lib"
    & cmd.exe /c "$cmd > `"$log`" 2>&1"
    if (-not (Test-Path $tmp)) {
        Write-Host "MSVC build FAILED - see $log" -ForegroundColor Red
        Get-Content $log -Tail 20 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkRed }
        exit 1
    }
}

# Verify what was produced rather than trusting the toolchain: a 64-bit DLL here
# fails to load in a way that looks like a game bug, and the five forwarded exports
# are what keep the game able to start at all.
$bytes = [IO.File]::ReadAllBytes($tmp)
$pe = [BitConverter]::ToInt32($bytes, 0x3c)
$machine = [BitConverter]::ToUInt16($bytes, $pe + 4)
if ($machine -ne 0x14c) {
    Write-Host ("ABORT: built for 0x{0:X} - i76.exe is 32-bit and cannot load it." -f $machine) -ForegroundColor Red
    exit 1
}
# Verified: now it is safe to replace the good binary.
Move-Item $tmp $out -Force
Write-Host ("Built Strlkup.dll ({0} bytes, x86) -> {1}" -f $bytes.Length, $here) -ForegroundColor Green

if ($Install) {
    $gd = ""
    $proc = Get-Process i76, nitro -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($proc) { try { $gd = Split-Path $proc.Path } catch { } }
    foreach ($c in @($GameDir, $gd, $env:I76_GAME_DIR,
        "C:\Users\james\Downloads\Interstate76-i76-everywhere-portable-20260801\Interstate 76",
        "C:\Games\Interstate 76")) {
        if ($c -and (Test-Path (Join-Path $c 'i76.exe'))) { $gd = $c; break }
    }
    if (-not $gd) {
        Write-Host "Could not find the game folder. Pass -GameDir or set I76_GAME_DIR." -ForegroundColor Yellow
        exit 1
    }
    if (-not (Test-Path (Join-Path $gd 'strlkup_orig.dll'))) {
        Write-Host "strlkup_orig.dll missing - the original was never backed up. Run setup-windows.ps1 first." -ForegroundColor Red
        exit 1
    }

    # The game holds Strlkup.dll open while it runs, so the copy fails - and this
    # used to print "installed" anyway, because Copy-Item's error was never checked.
    # That is how you end up testing a STALE dll and concluding the source change did
    # nothing. Refuse up front, and verify the bytes afterwards.
    if ($proc) {
        Write-Host "i76 is RUNNING - it holds Strlkup.dll open and the install would fail." -ForegroundColor Red
        Write-Host "  close the game (or: Stop-Process -Name i76 -Force) and run this again." -ForegroundColor DarkGray
        exit 1
    }
    $dest = Join-Path $gd 'Strlkup.dll'
    try { Copy-Item $out $dest -Force -ErrorAction Stop }
    catch { Write-Host "install FAILED: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }

    # Confirm what actually landed. A copy that silently did not happen is the
    # failure mode this whole block exists to prevent.
    $a = (Get-FileHash $out  -Algorithm MD5).Hash
    $b = (Get-FileHash $dest -Algorithm MD5).Hash
    if ($a -ne $b) {
        Write-Host "install VERIFY FAILED - destination does not match the build." -ForegroundColor Red
        Write-Host "  built $a`n  dest  $b" -ForegroundColor DarkRed
        exit 1
    }
    Write-Host "installed -> $dest  (verified $($a.Substring(0,8)))" -ForegroundColor Green
    Write-Host "Revert: copy strlkup_orig.dll over Strlkup.dll. Restart the game." -ForegroundColor Cyan
}
