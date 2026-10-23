#!/bin/bash
set -e
echo "============================================"
echo " Building Convertor.app for macOS"
echo "============================================"

echo "[1/3] Installing PyInstaller..."
python3 -m pip install --upgrade -r requirements-dev.txt

echo ""
echo "[2/3] Building (this takes 3-5 minutes)..."
python3 -m PyInstaller Convertor.spec --noconfirm --clean

echo ""
echo "[3/3] Done!"
echo ""
echo "Your app is at:"
echo "    dist/Convertor.app"
echo ""
echo "To zip it for sending:"
echo "    ditto -c -k --sequesterRsrc --keepParent dist/Convertor.app Convertor-mac.zip"
echo ""
echo "NOTE: First launch she'll need to right-click the app,"
echo "      click 'Open', then 'Open' again (macOS security)."
echo ""