<#
  cd2-test.ps1 - the "Please insert CD 2" prompt (backlog P1-09): launch the PRISTINE exe with the game folder NOT
  the working directory (the launch style that prompted in sitting 1), with the proxy's CD instrument
  (I76_CD_LOG, always on) and then again with the mitigation I76_CD_FAKE=1. Reads the proxy log lines
  (MSGBOX / CD PROMPT / startup_IsMinimum / CD FAKE) and kills the game. Sandbox only.

    .\cd2-test.ps1 [-Exe i76_pristine_fix.exe] [-Cwd C:\Windows] [-Wait 25]
#>
param([string]$Exe = "i76_pristine_fix.exe", [string]$Cwd = "C:\Windows", [int]$Wait = 25)
$ErrorActionPreference = "Continue"
$G = "C:\Users\james\i76-uncap-lab\game"; $log = "$G\mciproxy.log"
if (Get-Process i76* -ErrorAction SilentlyContinue) { "game running - abort"; exit 1 }
Copy-Item "$G\STRLKUP.DLL" "$G\STRLKUP.DLL.pretest" -Force
Copy-Item "C:\Users\james\i76-everywhere\music-fix\Strlkup.dll" "$G\STRLKUP.DLL" -Force
Set-Content "$G\.console-test.lock" "cd2 test $PID"
try {
    foreach ($fake in "", "1") {
        $len = (Get-Item $log).Length
        $psi = New-Object Diagnostics.ProcessStartInfo
        $psi.FileName = "$G\$Exe"; $psi.Arguments = "-glide"; $psi.WorkingDirectory = $Cwd; $psi.UseShellExecute = $false
        $psi.EnvironmentVariables["I76MUSIC_LOG"] = "1"
        if ($fake) { $psi.EnvironmentVariables["I76_CD_FAKE"] = $fake }
        $p = [Diagnostics.Process]::Start($psi)
        Start-Sleep -Seconds $Wait; $p.Refresh()
        "--- $Exe cwd=$Cwd I76_CD_FAKE='$fake': exited=$($p.HasExited) title='$($p.MainWindowTitle)'"
        $b = [IO.File]::ReadAllBytes($log)
        $new = [Text.Encoding]::GetEncoding(28591).GetString($b, $len, $b.Length - $len)
        ($new -split "`n") | Where-Object { $_ -match "MSGBOX|CD PROMPT|startup_IsMinimum|CD FAKE|cd-log|shell_cb_17|NOTE" } |
            Select-Object -First 14 | ForEach-Object { "  " + $_.Substring(0, [Math]::Min(190, $_.Length)) }
        if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }
        Start-Sleep -Seconds 2
    }
} finally {
    Copy-Item "$G\STRLKUP.DLL.pretest" "$G\STRLKUP.DLL" -Force; Remove-Item "$G\STRLKUP.DLL.pretest"
    Remove-Item "$G\.console-test.lock" -ErrorAction SilentlyContinue
    "restored"
}
