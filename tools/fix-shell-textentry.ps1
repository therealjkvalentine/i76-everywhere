<#
  fix-shell-textentry.ps1 - repair typing on the bookmark save screen.

  SYMPTOM
    On the Save Bookmark screen you can type at most one character, usually none, and the
    overwrite prompt cannot be answered. It looks intermittent because it depends on stale
    stack contents.

  CAUSE
    i76shell.dll's key-to-character routine (+0x1C12B) zeroes a stack buffer before calling
    ToAscii. Two bytes in the widely circulated patched shell narrow that clear:

        stock   mov ecx, 0x41   /  lea edi, [esp+8]     zeroes esp+8 .. esp+0x10B
        patched mov ecx, 0x40   /  lea edi, [esp+0xC]   zeroes esp+0xC .. esp+0x10B

    esp+8 is the WORD that ToAscii writes the character into; esp+0xC is the 256-byte key
    state array. (esp+0xC is confirmed as the key-state base by the instruction at +0x1C14C,
    `mov byte [esp+0x1C], 0x80`, which sets keystate[VK_SHIFT=0x10].) The stock bounds cover
    the output word AND the key state exactly - 4 + 256 = 260 = 0x104 bytes - and overrun
    nothing, so the "out-of-bounds write" the narrowing was meant to fix does not appear to
    exist.

    What the narrowing does do is leave the output word uninitialised. The routine then reads
    it back as a full 16 bits:

        +0x1C16F  mov eax, [esp+8]
        +0x1C173  and eax, 0xffff

    so a keystroke arrives as 0xB261 instead of 0x0061 - 'a' with a garbage high byte - and
    the name field rejects it. Measured live before the fix:

        ToAscii vk=0x41 -> 1 char=0xB261        ToAscii vk=0x0D -> 1 char=0xE90D

    and after:

        ToAscii vk=0x48 -> 1 char=0x0068        ToAscii vk=0x0D -> 1 char=0x000D

    It is intermittent because stale stack is occasionally zero, which is the one character
    that sometimes gets through.

  This script restores the stock two bytes. It verifies before and after, and backs the file
  up to i76shell.dll.pre-toascii-fix. Re-running it is safe: an already-correct file is left
  alone.
#>
param(
    [Parameter(Mandatory)] [string]$GameDir,
    [switch]$Revert
)
$ErrorActionPreference = 'Stop'

$dll = Join-Path $GameDir 'i76shell.dll'
if (-not (Test-Path $dll)) { throw "no i76shell.dll in $GameDir" }
if (Get-Process i76 -EA SilentlyContinue) { throw "close the game first - the DLL is in use" }

# file offsets; RVA = file + 0xC00 in this build's .text
$SITES = @(
    @{ Off = 0x1B52C; Stock = 0x41; Broken = 0x40; What = 'mov ecx,0x41 (clear 260 bytes, not 256)' },
    @{ Off = 0x1B535; Stock = 0x08; Broken = 0x0C; What = 'lea edi,[esp+8] (include the ToAscii output word)' }
)
$want = if ($Revert) { 'Broken' } else { 'Stock' }
$from = if ($Revert) { 'Stock' }  else { 'Broken' }

$b = [IO.File]::ReadAllBytes($dll)
$todo = @()
foreach ($s in $SITES) {
    $cur = $b[$s.Off]
    if     ($cur -eq $s[$want])  { Write-Host ("  0x{0:X6} already 0x{1:X2} - {2}" -f $s.Off, $cur, $s.What) -ForegroundColor DarkGray }
    elseif ($cur -eq $s[$from])  { $todo += $s }
    else { throw ("0x{0:X6} holds 0x{1:X2}; expected 0x{2:X2} or 0x{3:X2}. This is not a shell build this script knows - not touching it." -f $s.Off, $cur, $s.Stock, $s.Broken) }
}
if (-not $todo) { Write-Host "nothing to do - already correct." -ForegroundColor Green; exit 0 }

$backup = "$dll.pre-toascii-fix"
if (-not (Test-Path $backup)) { Copy-Item $dll $backup; Write-Host "  backed up -> $backup" -ForegroundColor DarkGray }

foreach ($s in $todo) {
    $b[$s.Off] = $s[$want]
    Write-Host ("  0x{0:X6}: 0x{1:X2} -> 0x{2:X2}   {3}" -f $s.Off, $s[$from], $s[$want], $s.What)
}
[IO.File]::WriteAllBytes($dll, $b)

# read back from disk - never trust the write
$v = [IO.File]::ReadAllBytes($dll)
foreach ($s in $SITES) {
    if ($v[$s.Off] -ne $s[$want]) { throw ("verify failed at 0x{0:X6}: 0x{1:X2}" -f $s.Off, $v[$s.Off]) }
}
Write-Host ("text entry {0}." -f $(if ($Revert) { 'reverted to the patched (broken) bytes' } else { 'repaired - verified on disk' })) -ForegroundColor Green
