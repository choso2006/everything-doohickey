@echo off
title Building Convertor for Windows
echo ============================================
echo  Building Convertor.exe for Windows
echo ============================================
echo.

if not exist "bin\mpv.exe" (
    echo NOTE: bin\mpv.exe not found.
    echo For the in-app video player, download mpv from:
    echo     https://mpv.io/installation/
    echo Put mpv.exe inside a folder called "bin" next to this script.
    echo.
    echo Without it, the build still works but the video player
    echo falls back to ffplay ^(no embedded controls^).
    echo.
    timeout /t 5 >nul
    if not exist "bin" mkdir bin
) else (
    echo Found bin\mpv.exe — will be bundled with the app.
    echo.
)

echo [1/3] Installing PyInstaller...
py -m pip install --upgrade -r requirements-dev.txt
if errorlevel 1 goto :fail

echo.
echo [2/3] Building (this takes 3-5 minutes)...
py -m PyInstaller Convertor.spec --noconfirm --clean
if errorlevel 1 goto :fail

echo.
echo [3/3] Done!
echo.
echo Your app is here:
echo     dist\Convertor\Convertor.exe
echo.
echo Zip that whole "dist\Convertor" folder and send it.
echo.
pause
exit /b 0

:fail
echo.
echo Build FAILED. Scroll up to see the error.
pause
exit /b 1