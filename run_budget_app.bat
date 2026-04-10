@echo off
setlocal

set "APP_DIR=%~dp0"

if exist "%USERPROFILE%\miniconda3\python.exe" (
  "%USERPROFILE%\miniconda3\python.exe" "%APP_DIR%app.py"
  goto :eof
)

python "%APP_DIR%app.py"
