@echo off
title Building Convertor for Windows
echo ============================================
echo  Building Convertor.exe for Windows
echo ============================================
echo.

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