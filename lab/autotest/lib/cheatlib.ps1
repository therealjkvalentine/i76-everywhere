<#
  cheatlib.ps1 — send Interstate '76's debug/cheat key combinations.

  Source: CahootsMalone/interstate-76-stuff (indexed in i76-everywhere COMMUNITY-RESOURCES.md).
  The one that matters for automated testing is SELF-DETONATE: it kills the player on demand,
  which is the only reliable way to reach the post-death camera. Melee AI cannot do it — 400 s
  of deliberately ramming enemy cars left the player entity untouched.

    . .\lib\cheatlib.ps1
    Send-SelfDestruct          # CTRL+ALT+X - blows up the player's car

  Chorded keys go through keybd_event with SCANCODES like every other input here; DirectInput
  ignores posted WM_KEY messages. The modifiers must be held across the X press and released in
  reverse order, or the game sees a bare X.
#>
. "$PSScriptRoot\inputlib.ps1"

$VK_CTRL = [byte]0x11
$VK_ALT  = [byte]0x12
$VK_X    = [byte]0x58

function Send-SelfDestruct {
    param([int]$HoldMs = 90)
    Key-Down $VK_CTRL; Start-Sleep -Milliseconds 40
    Key-Down $VK_ALT;  Start-Sleep -Milliseconds 40
    Key-Down $VK_X;    Start-Sleep -Milliseconds $HoldMs
    Key-Up   $VK_X;    Start-Sleep -Milliseconds 30
    Key-Up   $VK_ALT;  Start-Sleep -Milliseconds 30
    Key-Up   $VK_CTRL
}

# The typed cheat codes are held with CTRL+SHIFT while the letters are typed.
#   getdown  - mission succeeds when your vehicle is destroyed; all vehicles turn hostile
#   blflat / brflat / flflat / frflat - destroy one named tire
#   wiggleburger - persistent double-vision effect
function Send-CheatCode {
    param([Parameter(Mandatory = $true)][string]$Code)
    $VK_SHIFT = [byte]0x10
    Key-Down $VK_CTRL; Key-Down $VK_SHIFT; Start-Sleep -Milliseconds 60
    foreach ($ch in $Code.ToUpper().ToCharArray()) {
        Send-Key ([byte][char]$ch) 50
        Start-Sleep -Milliseconds 45
    }
    Key-Up $VK_SHIFT; Key-Up $VK_CTRL
}
