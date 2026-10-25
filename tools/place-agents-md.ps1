<#
.SYNOPSIS  Write AGENTS.md (from docs\AGENTS-GAME-FOLDER.md, filled per folder) into the root of one kept game folder.
.EXAMPLE   .\place-agents-md.ps1 -Dir (Join-Path $env:USERPROFILE 'Games\I76\Interstate 76 Gold') -Role 'main' -Game Gold
#>
param([Parameter(Mandatory)][string]$Dir, [Parameter(Mandatory)][ValidateSet('dev','test','main')][string]$Role, [Parameter(Mandatory)][ValidateSet('Gold','Nitro')][string]$Game,
      [string]$Template = (Join-Path $PSScriptRoot '..\docs\AGENTS-GAME-FOLDER.md'))
$ErrorActionPreference = 'Stop'
$name = Split-Path $Dir -Leaf
$sub  = if ($Game -eq 'Gold') { 'Interstate 76' } else { 'Interstate 76 Nitro Pack' }
$dll  = if ($Game -eq 'Gold') { 'STRLKUP.DLL' } else { 'strlkup.dll' }
$exe  = if ($Game -eq 'Gold') { 'i76.exe' } else { 'nitro.exe' }
$gd   = Join-Path $Dir $sub
$md5  = if (Test-Path "$gd\$dll") { (Get-FileHash "$gd\$dll" -Algorithm MD5).Hash.Substring(0,8).ToLower() } else { 'n/a' }
$bats = (Get-ChildItem $Dir -Filter '*.bat' -File | Sort-Object Name | ForEach-Object { '`' + $_.Name + '`' }) -join ', '
$roleText = switch ($Role) {
  'main' { "**main** - the owner's playable copy ('$name'), the only one the owner plays; never experiment in it, change it only by a gated promotion from test" }
  'dev'  { "**dev** - the one working copy lanes build into; nothing is run from here for an owner test" }
  'test' { "**test** - the gate twin: lanes copy it (<lane>-YYYYMMDD), gate on the copy, delete the copy at lane end" }
}
$loc = @{ main = (Join-Path $env:USERPROFILE 'Games\I76'); dev = (Join-Path $env:USERPROFILE 'i76-uncap-lab'); test = (Join-Path $env:USERPROFILE 'i76-uncap-lab') }[$Role]
$t = Get-Content $Template -Raw
$tail = $t.Substring($t.IndexOf('## Troubleshooting'))
$head = @"
# AGENTS.md - $name ($Game, $Role)

Latest information: https://github.com/therealjkvalentine/i76-everywhere (docs/, docs/records/, tools/). This file is a pointer, not the source of truth.

## What this folder is
- Folder: ``$Dir``. Tiers per game: **dev** (lab ``dev-$($Game.ToLower())``), **test** (lab ``test-$($Game.ToLower())``), **main** (``Games\I76\Interstate 76 $Game``). No separate golden/reference copy (archived on D:).
- Role: $roleText. Game: **$Game**. Proxy md5 of ``$sub\$dll`` right now: **$md5** (``$exe`` is the game). See ``VERSION.md`` where present.
- Launchers here: $bats. (``README.md`` in ``Games\I76`` has the owner-facing table.)
- Where things are: proxy ``$sub\$dll`` (``strlkup_orig.dll`` = the real original); presets ``$sub\presets\*.psd1``; launcher ``$sub\PLAY-i76.ps1`` (Gold); dgVoodoo ``dgVoodoo.conf``; controls ``$sub\input.map``; log ``$sub\mciproxy.log`` (rotates; look for the ``CRASH`` line); rollbacks ``_rollback\``.
- Originals stay: ``strlkup_orig.dll``, ``i76.exe.u32xorig``, ``i76shell.dll.orig``, one ``input.map`` known-good backup. Cruft (``*.pre-*``, ``*.driver-*``, ``STRLKUP.DLL.<md5>`` backups, old logs) was moved to ``D:\i76-archive\cruft-20261025\<folder>\`` on 2026-10-25 and can be fetched from there.
- Old names (``exp-polish2``, ``rc-twin-20261024``, ``release-candidate``, ``exp-nitro-*``) are junctions to the new folders; see ``docs\COPIES-PLAN-2026-10-24.md`` (Done 2026-10-25).

"@
Set-Content -Path (Join-Path $Dir 'AGENTS.md') -Value ($head + $tail) -Encoding UTF8
Write-Host "wrote $Dir\AGENTS.md (proxy $md5)"
