# build.ps1 - rebuild the pass-4 Ghidra project from clean and export it (Task 2, method doc section 7).
# Reproduces recon-2026-09-04\recon\fp-ghidra passes 3 -> 4a -> 4b on the pristine exe:
#   step 1  -import  with prescript EnableAggressive (Aggressive Instruction Finder + Decompiler Parameter ID)
#   step 2  -process (re-analysis) + postScript CreateFuncsFromDataPtrs (then Ghidra's post-script analysis)
#   step 3  -process (re-analysis) + postScript ExportBaseline <out> + postScript DumpAll.py <out>
# Usage: powershell -ExecutionPolicy Bypass -File build.ps1 -Proj <projdir> -Out <exportdir> [-Exe <exe>] [-Name i76map]
param(
    [string]$Proj = "C:\Users\james\i76-map\ghidra\proj",
    [string]$Out  = "C:\Users\james\i76-map\ghidra\export",
    [string]$Exe  = "C:\Users\james\i76-map\ghidra\i76_ref.exe",
    [string]$Name = "i76map",
    [string]$Scripts = "C:\Users\james\i76-map\ghidra\scripts",
    [switch]$Clean
)
$ErrorActionPreference = "Continue"
$hl = "C:\Users\james\Downloads\ghidra_11.4.1_PUBLIC_20250731\ghidra_11.4.1_PUBLIC\support\analyzeHeadless.bat"
$logdir = Join-Path $Out "logs"
if ($Clean) {
    if (Test-Path $Proj) { Remove-Item -Recurse -Force $Proj }
    # keep the directory's README.md (Task 0 owns it); remove every generated file
    if (Test-Path $Out)  { Get-ChildItem $Out -Force | Where-Object { $_.Name -ne "README.md" } | Remove-Item -Recurse -Force }
}
New-Item -ItemType Directory -Force $Proj | Out-Null
New-Item -ItemType Directory -Force $Out | Out-Null
New-Item -ItemType Directory -Force $logdir | Out-Null
$md5 = (Get-FileHash -Algorithm MD5 $Exe).Hash.ToLower()
"build start $(Get-Date -Format o) exe=$Exe md5=$md5 proj=$Proj out=$Out" | Tee-Object -FilePath (Join-Path $logdir "build.log")
$sw = [Diagnostics.Stopwatch]::StartNew()

"== step1 import + EnableAggressive ==" | Tee-Object -Append -FilePath (Join-Path $logdir "build.log")
& $hl $Proj $Name -import $Exe -preScript EnableAggressive.java -scriptPath $Scripts -log (Join-Path $logdir "step1.log") -scriptlog (Join-Path $logdir "step1_script.log") *> (Join-Path $logdir "step1_console.log")
"step1 exit=$LASTEXITCODE t=$($sw.Elapsed.TotalSeconds)" | Tee-Object -Append -FilePath (Join-Path $logdir "build.log")

"== step2 process + CreateFuncsFromDataPtrs ==" | Tee-Object -Append -FilePath (Join-Path $logdir "build.log")
& $hl $Proj $Name -process (Split-Path -Leaf $Exe) -postScript CreateFuncsFromDataPtrs.java -scriptPath $Scripts -log (Join-Path $logdir "step2.log") -scriptlog (Join-Path $logdir "step2_script.log") *> (Join-Path $logdir "step2_console.log")
"step2 exit=$LASTEXITCODE t=$($sw.Elapsed.TotalSeconds)" | Tee-Object -Append -FilePath (Join-Path $logdir "build.log")

"== step3 process + ExportBaseline + DumpAll ==" | Tee-Object -Append -FilePath (Join-Path $logdir "build.log")
& $hl $Proj $Name -process (Split-Path -Leaf $Exe) -postScript ExportBaseline.java $Out -postScript DumpAll.py $Out -scriptPath $Scripts -log (Join-Path $logdir "step3.log") -scriptlog (Join-Path $logdir "step3_script.log") *> (Join-Path $logdir "step3_console.log")
"step3 exit=$LASTEXITCODE t=$($sw.Elapsed.TotalSeconds)" | Tee-Object -Append -FilePath (Join-Path $logdir "build.log")
"build end $(Get-Date -Format o) total=$($sw.Elapsed.TotalSeconds)s" | Tee-Object -Append -FilePath (Join-Path $logdir "build.log")
