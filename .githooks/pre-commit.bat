@echo off

git branch --show-current | findstr /R "^main$" >nul
if %errorlevel%==0 (
    echo ERROR: Direct commits on main are blocked.
    exit /b 1
)

python -m ruff check .
if %errorlevel% neq 0 exit /b 1

python -m pytest
if %errorlevel% neq 0 exit /b 1
