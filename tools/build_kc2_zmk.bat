@echo off
setlocal EnableExtensions DisableDelayedExpansion

where wsl.exe >nul 2>nul
if errorlevel 1 (
    echo ERROR: WSL2 is not installed or wsl.exe is not on PATH.
    exit /b 1
)

wsl.exe --status >nul 2>nul
if errorlevel 1 (
    echo ERROR: WSL2 has no usable default Linux distribution.
    exit /b 1
)

for %%I in ("%~dp0..") do set "KC2_REPO_ROOT=%%~fI"
set "KC2_REPO_WSL="
for /f "usebackq delims=" %%I in (`wsl.exe wslpath -a "%KC2_REPO_ROOT%"`) do set "KC2_REPO_WSL=%%I"
if not defined KC2_REPO_WSL (
    echo ERROR: Failed to resolve the KC2 repository path in WSL2.
    exit /b 1
)

echo [1/2] Checking WSL2 build prerequisites...
wsl.exe -u root -- bash "%KC2_REPO_WSL%/tools/build_kc2_zmk_wsl.sh" --install-dependencies
if errorlevel 1 exit /b 1

echo [2/2] Building pristine KC2 left and right firmware...
wsl.exe -- bash "%KC2_REPO_WSL%/tools/build_kc2_zmk_wsl.sh" --build "%KC2_REPO_WSL%"
if errorlevel 1 exit /b 1

echo Built firmware\out\kc2_left.uf2 and firmware\out\kc2_right.uf2.
exit /b 0
