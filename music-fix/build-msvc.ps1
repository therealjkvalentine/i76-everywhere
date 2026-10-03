# build-msvc.ps1 - the MSVC x86 build of Strlkup.dll. Kept as an entry point for existing notes and habits;
# since 2026-10-02 it is build.ps1 -Msvc (the abort it was written to dodge is fixed there: the cmd redirect
# now covers vcvars32.bat as well as cl). Builds to Strlkup.build.dll, verifies x86, then replaces Strlkup.dll.
& (Join-Path $PSScriptRoot 'build.ps1') -Msvc @args
exit $LASTEXITCODE
