<#
  Build the base-game in-mission music fix: a proxy Strlkup.dll that IAT-hooks
  the game's cdaudio MCI calls and plays GOG's music\N.mp3 instead. See README.md.

  Needs a 32-bit GCC (w64devkit). A prebuilt Strlkup.dll is committed beside this
  script, so building is only necessary if you change strlkproxy.c.

  Usage:  ./build.ps1 [-Gcc "C:\Games\_tools\w64devkit\bin\gcc.exe"] [-Msvc] [-Install -GameDir <test copy>]

  -Install never falls back to the playable install: with no -GameDir it takes the running
  game's folder, then $env:I76_GAME_DIR, then the lab sandbox (..\..\i76-uncap-lab\game).
#>
param([string]$Gcc = "C:\Games\_tools\w64devkit\bin\gcc.exe", [switch]$Install,
      [switch]$Msvc,   # force the MSVC x86 branch even if gcc is present (what build-msvc.ps1 runs)
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
if (-not $Msvc -and (Test-Path $Gcc)) {
    & $Gcc -m32 -O2 -s -shared -o $tmp (Join-Path $here 'strlkproxy.c') (Join-Path $here 'strlkup.def')
    if ($LASTEXITCODE) { throw "gcc build failed ($LASTEXITCODE)" }
} else {
    # MSVC fallback. w64devkit is not installed here, but Visual Studio 2019 Build
    # Tools are, with an x86 cross-compiler - `cl.exe` simply is not on PATH, which
    # is not the same as absent (an assumption that cost a round elsewhere in this
    # repo). vcvars32.bat sets up the x86 environment.
    if (-not $Msvc) { Write-Host "gcc not at $Gcc - using MSVC x86 instead." -ForegroundColor DarkGray }
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

    # No linker forwarders: link.exe does not emit forwarders to another DLL from the .def or
    # from /EXPORT:name=strlkup_orig.name (five unresolved externals), so strlkproxy.c forwards
    # the five Strlkup exports itself (naked jmp stubs + an IAT repoint; see its comment block
    # "FORWARDING THE FIVE Strlkup EXPORTS WITHOUT LINKER FORWARDERS"). Nothing to pass here.

    # Redirection inside cmd, NOT `2>&1` in PowerShell: that wraps stderr in a
    # NativeCommandError and aborts under $ErrorActionPreference='Stop' even on a
    # successful compile (vcvars emits a benign vswhere warning).
    $cmd = "call `"$vcvars`" && cd /d `"$here`" && " +
           "cl /nologo /LD /MT /O2 /W3 /D_CRT_SECURE_NO_WARNINGS strlkproxy.c " +
           "/Fe:`"$tmp`" /link user32.lib"
    # The parentheses matter: without them the redirect binds to cl only, vcvars' warning still
    # lands on PowerShell's stderr, and under 'Stop' with a captured stderr (an agent's tool
    # call, a CI runner, `2>&1`) the script aborted before cl ran. That was this branch's bug
    # until 2026-10-02 (build-msvc.ps1 existed to dodge it). Belt and braces: 'Continue' for
    # the one native call.
    $ErrorActionPreference = 'Continue'
    & cmd.exe /c "($cmd) > `"$log`" 2>&1"
    $ErrorActionPreference = 'Stop'
    Get-Content $log -ErrorAction SilentlyContinue | Select-String 'warning|error' |
        Where-Object { $_ -notmatch 'vswhere' } | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
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
        (Join-Path $here '..\..\i76-uncap-lab\game'))) {
        # The daily driver and C:\Games\Interstate 76 were in this list until 2026-10-02: a bare
        # -Install could put a fresh, unverified build on the install being played on (AGENTS.md).
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
