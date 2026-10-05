# setup-sshd-windows.ps1 - enable Windows' built-in OpenSSH server for LAN access from the MacBook.
# Run from an ELEVATED PowerShell (one UAC prompt):
#     powershell -ExecutionPolicy Bypass -File tools\setup-sshd-windows.ps1 [-PubKeyFile <path to the Mac's id_ed25519.pub>]
# What it does: installs the OpenSSH.Server capability, starts sshd and sets it to Automatic, turns password login
# OFF (keys only), makes PowerShell the login shell, adds the given public key for this administrator account
# (C:\ProgramData\ssh\administrators_authorized_keys, ACL Administrators + SYSTEM only), and limits the firewall rule
# to the home LAN (192.168.1.0/24). Undo: Stop-Service sshd; Set-Service sshd -StartupType Disabled;
# Remove-NetFirewallRule -Name OpenSSH-Server-In-TCP-LAN.
param([string]$PubKeyFile = "", [string]$Subnet = "192.168.1.0/24")
$ErrorActionPreference = 'Stop'
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Run this from an elevated PowerShell (right-click > Run as administrator)." -ForegroundColor Red; exit 1 }

$cap = Get-WindowsCapability -Online -Name 'OpenSSH.Server*' | Select-Object -First 1
if ($cap.State -ne 'Installed') { Write-Host "installing $($cap.Name) ..."; Add-WindowsCapability -Online -Name $cap.Name | Out-Null }
Start-Service sshd; Set-Service sshd -StartupType Automatic        # first start writes C:\ProgramData\ssh\sshd_config

$cfg = 'C:\ProgramData\ssh\sshd_config'
$t = Get-Content $cfg -Raw
foreach ($kv in @(@('PasswordAuthentication', 'no'), @('PubkeyAuthentication', 'yes'), @('KbdInteractiveAuthentication', 'no'))) {
    $re = '(?m)^#?\s*' + $kv[0] + '\s+.*$'
    if ($t -match $re) { $t = [regex]::Replace($t, $re, "$($kv[0]) $($kv[1])") } else { $t = "$($kv[0]) $($kv[1])`r`n" + $t }
}
Set-Content $cfg $t -Encoding ascii

New-ItemProperty -Path 'HKLM:\SOFTWARE\OpenSSH' -Name DefaultShell -Value 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -PropertyType String -Force | Out-Null

if ($PubKeyFile) {
    $ak = 'C:\ProgramData\ssh\administrators_authorized_keys'
    $key = (Get-Content $PubKeyFile -Raw).Trim()
    if ($key -notmatch '^ssh-(ed25519|rsa) ') { Write-Host "that does not look like a public key: $PubKeyFile" -ForegroundColor Red; exit 1 }
    if (-not (Test-Path $ak) -or -not (Select-String -Path $ak -SimpleMatch $key -Quiet)) { Add-Content $ak $key -Encoding ascii }
    icacls $ak /inheritance:r /grant 'Administrators:F' /grant 'SYSTEM:F' | Out-Null
    Write-Host "key added to $ak"
}

Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue | Disable-NetFirewallRule
if (-not (Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP-LAN' -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name 'OpenSSH-Server-In-TCP-LAN' -DisplayName 'OpenSSH Server (sshd), home LAN only' -Enabled True `
        -Direction Inbound -Protocol TCP -LocalPort 22 -RemoteAddress $Subnet -Action Allow | Out-Null }

Restart-Service sshd
Write-Host ("sshd: {0}, startup {1}; passwords off; firewall: port 22 from {2} only" -f (Get-Service sshd).Status, (Get-Service sshd).StartType, $Subnet) -ForegroundColor Green
