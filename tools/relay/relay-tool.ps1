<#
  relay-tool.ps1 - what RUN-RELAY.bat and RELAY-FIREWALL.bat do (tools\relay\README.md). Windows PowerShell 5.1.

    relay-tool.ps1 -Run              start pyrelay.py in this console: prints the port, this PC's addresses and the public address
    relay-tool.ps1 -Firewall         (as administrator) remove every inbound BLOCK rule for the relay's Python, add one inbound ALLOW
                                     rule for UDP <port> on that Python, private + public profiles
    relay-tool.ps1 -Firewall -Check  list what -Firewall would remove / add; changes nothing (no administrator needed)
    relay-tool.ps1 -Info             the Python, its real program file and the port, then exit

  The Python: relay.ini "python =" if set, else the py launcher (py -3), else python. The firewall needs the REAL program file
  (a Microsoft Store Python's "python.exe" is an alias; the process runs from C:\Program Files\WindowsApps\...\python3.x.exe),
  so it is read from a running Python (QueryFullProcessImageNameW on itself).
#>
param([switch]$Run, [switch]$Firewall, [switch]$Check, [switch]$Info)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$ini = Join-Path $here 'relay.ini'
$ruleName = 'Interstate 76 relay (i76-everywhere)'

function Get-IniValue([string]$key, [string]$default) {
    if (-not (Test-Path -LiteralPath $ini)) { return $default }
    foreach ($l in Get-Content -LiteralPath $ini) {
        $t = $l.Trim()
        if ($t -match "^(?i)$([regex]::Escape($key))\s*=\s*(.*)$") {
            $v = ($Matches[1] -replace '\s+[#;].*$', '').Trim().Trim('"')
            if ($v) { return $v }
        }
    }
    return $default
}

$port = [int](Get-IniValue 'port' '19900')
$pyCfg = Get-IniValue 'python' ''
$probe = 'import ctypes,sys; k=ctypes.windll.kernel32; b=ctypes.create_unicode_buffer(1024); n=ctypes.c_ulong(1024); k.QueryFullProcessImageNameW(ctypes.c_void_p(-1),0,b,ctypes.byref(n)); print(sys.executable); print(b.value); print(sys.version.split()[0])'
$py = $null; $pyArgs = @(); $real = $null; $ver = $null
$cands = @()
if ($pyCfg) { $cands += , @($pyCfg) } else { $cands += , @('py', '-3'); $cands += , @('python') }
foreach ($c in $cands) {
    try {
        $exe = $c[0]; $pre = @($c | Select-Object -Skip 1)
        $out = @(& $exe @pre -c $probe 2>$null)
        if ($LASTEXITCODE -eq 0 -and $out.Count -ge 3 -and $out[1]) { $py = $out[0].Trim(); $real = $out[1].Trim(); $ver = $out[2].Trim(); break }
    } catch { }
}
if (-not $py) {
    Write-Host 'No Python 3 found. Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH"), or set' -ForegroundColor Red
    Write-Host "  python = <full path to python.exe>   in $ini" -ForegroundColor Red
    exit 1
}
$store = $real -match '(?i)\\WindowsApps\\'

if ($Info) {
    "python  $py ($ver)"; "program $real"; "port    UDP $port"
    if ($store) { 'note    a Microsoft Store Python: its program folder changes at each update (run RELAY-FIREWALL.bat again after one)' }
    exit 0
}

if ($Firewall) {
    Write-Host "Relay program: $real (Python $ver)" -ForegroundColor Cyan
    Write-Host "Relay port:    UDP $port (relay.ini)" -ForegroundColor Cyan
    # every inbound rule on this program file (netsh lists them all; no admin needed to read)
    $txt = (netsh advfirewall firewall show rule name=all dir=in verbose) -join "`n"
    $rules = @()
    foreach ($b in ($txt -split "`n(?=Rule Name:)")) {
        $f = @{}
        foreach ($l in ($b -split "`n")) { if ($l -match '^([A-Za-z ]+):\s+(.*)$') { $f[$Matches[1].Trim()] = $Matches[2].Trim() } }
        if ($f['Program'] -and ($f['Program'] -ieq $real)) { $rules += [pscustomobject]@{ Name = $f['Rule Name']; Action = $f['Action']; Profiles = $f['Profiles']; Protocol = $f['Protocol']; Port = $f['LocalPort']; Enabled = $f['Enabled'] } }
    }
    $blocks = @($rules | Where-Object { $_.Action -eq 'Block' })
    $ours = @($rules | Where-Object { $_.Name -eq $ruleName })
    Write-Host ''
    Write-Host "Inbound rules on that program now: $($rules.Count)"
    foreach ($r in $rules) { Write-Host ("  {0,-6} {1,-40} {2,-15} {3} port {4}" -f $r.Action, $r.Name, $r.Profiles, $r.Protocol, $r.Port) }
    if ($Check) {
        Write-Host ''
        Write-Host ("-Check: would remove {0} BLOCK rule(s) and {1} old copy(ies) of '{2}', then add '{2}': allow inbound UDP {3}, private + public." -f $blocks.Count, $ours.Count, $ruleName, $port) -ForegroundColor Yellow
        Write-Host 'Nothing was changed.' -ForegroundColor Yellow
        exit 0
    }
    $admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $admin) { Write-Host 'Needs administrator rights: run RELAY-FIREWALL.bat (it asks for them).' -ForegroundColor Red; exit 1 }
    # remove the inbound BLOCK rules on this program file (the ones Windows makes when its "allow access?" prompt is dismissed)
    $mine = @(Get-NetFirewallApplicationFilter -PolicyStore ActiveStore | Where-Object { $_.Program -ieq $real } | Get-NetFirewallRule -PolicyStore ActiveStore -ErrorAction SilentlyContinue |
              Where-Object { $_.Direction -eq 'Inbound' -and $_.Action -eq 'Block' })
    foreach ($r in $mine) {
        try { Remove-NetFirewallRule -Name $r.Name -ErrorAction Stop; Write-Host ("removed: BLOCK '{0}' ({1})" -f $r.DisplayName, $r.Profile) -ForegroundColor Green }
        catch { Write-Host ("could not remove BLOCK '{0}': {1} (a rule from Group Policy cannot be removed here)" -f $r.DisplayName, $_.Exception.Message) -ForegroundColor Red }
    }    & netsh advfirewall firewall delete rule name="$ruleName" | Out-Null
    & netsh advfirewall firewall add rule name="$ruleName" dir=in action=allow program="$real" protocol=udp localport=$port profile=private,public enable=yes description="i76-everywhere: the Interstate '76 internet relay (tools\relay\pyrelay.py), UDP $port. Private + public: the rule must hold whichever profile Windows gave the network the players' packets arrive on." | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Host 'Failed to add the allow rule.' -ForegroundColor Red; exit 1 }
    Write-Host ("added: ALLOW '{0}' inbound UDP {1} for {2}, private + public" -f $ruleName, $port, $real) -ForegroundColor Green
    if ($store) { Write-Host 'This is a Microsoft Store Python: after it updates, run RELAY-FIREWALL.bat again (the program folder changes).' -ForegroundColor Yellow }
    Write-Host "Undo: netsh advfirewall firewall delete rule name=`"$ruleName`"   (the removed BLOCK rules are not put back by that)"
    exit 0
}

if ($Run) {
    $Host.UI.RawUI.WindowTitle = "Interstate '76 relay - UDP $port"
    Write-Host "Interstate '76 internet relay" -ForegroundColor Cyan
    Write-Host "  port:   UDP $port   (relay.ini; the router forwards this port to this PC)"
    $lan = @()
    try { $lan = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop | Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' -and $_.InterfaceAlias -notmatch '(?i)vEthernet|WSL|Loopback' } | ForEach-Object { "$($_.IPAddress) ($($_.InterfaceAlias))" }) } catch { }
    Write-Host "  this PC on the home network: $(if ($lan) { $lan -join ', ' } else { '(not found)' })  <- the port forward points here"
    $pub = $null
    try { $pub = (Resolve-DnsName -Name myip.opendns.com -Server resolver1.opendns.com -Type A -DnsOnly -ErrorAction Stop | Where-Object { $_.IPAddress } | Select-Object -First 1).IPAddress } catch { }
    if ($pub) {
        Write-Host "  public address (asked OpenDNS): $pub" -ForegroundColor Green
        Write-Host "  players start:  PLAY.bat --relay ${pub}:$port   (PLAY-Nitro.bat for the Nitro Pack)" -ForegroundColor Green
    } else {
        Write-Host '  public address: not found here - your router''s status page shows it ("WAN" / "Internet" address), or search "what is my ip".' -ForegroundColor Yellow
        Write-Host "  players start:  PLAY.bat --relay <public address>:$port" -ForegroundColor Yellow
    }
    Write-Host '  A VPN app on this PC changes the public address and can stop forwarded packets: turn it off while hosting.' -ForegroundColor DarkGray
    Write-Host '  Every player in a session can see every other player''s internet address (the protocol carries it).' -ForegroundColor DarkGray
    Write-Host "  python: $py ($ver)$(if ($store) { ' - Microsoft Store Python' })" -ForegroundColor DarkGray
    Write-Host '  Close this window or press Ctrl+C to stop the relay.' -ForegroundColor DarkGray
    Write-Host ''
    & $py -I (Join-Path $here 'pyrelay.py') --config $ini
    exit $LASTEXITCODE
}

Write-Host 'relay-tool.ps1 -Run | -Firewall [-Check] | -Info (RUN-RELAY.bat / RELAY-FIREWALL.bat call it)'
exit 2
