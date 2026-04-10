@echo off
setlocal

set "APP_DIR=%~dp0"

if exist "%USERPROFILE%\miniconda3\python.exe" (
  "%USERPROFILE%\miniconda3\python.exe" "%APP_DIR%telegram_budget_service.py"
  goto :eof
)

python "%APP_DIR%telegram_budget_service.py"
