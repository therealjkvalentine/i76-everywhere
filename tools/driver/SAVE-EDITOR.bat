@echo off
REM Interstate '76 save editor ("Salvage Ledger") for THIS folder's saves.
REM Opens your browser on http://127.0.0.1:7676/ with the bookmarks in "Interstate 76" listed.
REM Every write keeps a .pre-edit and a timestamped .bak copy beside the save; deletes are renames, so
REM History / restore in the page can always undo. Close this window to stop the editor.
REM Close the game first: it rewrites the saves while running.
REM Needs Python 3 (python.org build). No packages to install.
setlocal
tasklist /FI "IMAGENAME eq i76.exe" | find /I "i76.exe" >nul && (echo The game is running - close it first, then run this again.& pause & exit /b 1)
set "SRV=%~dp0i76-save-editor-server.py"
if not exist "%SRV%" (echo Missing %SRV% & pause & exit /b 1)
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 "%SRV%" --dir "%~dp0Interstate 76" %*
) else (
  python "%SRV%" --dir "%~dp0Interstate 76" %*
)
if errorlevel 1 (
  echo.
  echo The save editor exited with an error - is Python 3 installed and on the PATH, and is port 7676 free?
  pause
)
endlocal
