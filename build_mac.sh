#!/bin/bash
set -e
echo "============================================"
echo " Building Convertor.app for macOS"
echo "============================================"

# ----- 1. mpv + dylibbundler ----------------------------------------------
echo ""
echo "Installing mpv + dylibbundler via Homebrew (for local build)..."
brew install mpv dylibbundler || brew upgrade mpv dylibbundler || true

mkdir -p bin/libs
MPV_BIN="$(command -v mpv || true)"
if [ -n "$MPV_BIN" ]; then
    cp "$MPV_BIN" bin/mpv
    chmod +x bin/mpv
    echo "Bundling dylibs with dylibbundler..."
    dylibbundler -od -b -x bin/mpv -d bin/libs -p @executable_path/libs/ || {
        echo "WARNING: dylibbundler failed"
    }
    echo ""
    echo "=== otool -L bin/mpv ==="
    otool -L bin/mpv || true
else
    echo "WARNING: mpv not installed. Video player will fall back to ffplay."
fi

# ----- 2. Install PyInstaller --------------------------------------------
echo ""
echo "[1/3] Installing PyInstaller..."
python3 -m pip install --upgrade -r requirements-dev.txt

# ----- 3. Build ----------------------------------------------------------
echo ""
echo "[2/3] Building (this takes 3-5 minutes)..."
python3 -m PyInstaller Convertor.spec --noconfirm --clean

# ----- 4. Ad-hoc sign everything -----------------------------------------
echo ""
echo "[2.5/3] Signing bundle (ad-hoc)..."
BUNDLE="dist/Convertor.app"

MPV_PATH=$(find "$BUNDLE" -name mpv -type f 2>/dev/null | head -1)
if [ -n "$MPV_PATH" ]; then
    codesign --force --sign - "$MPV_PATH" || true
fi

LIBS_DIR=$(find "$BUNDLE" -name "libs" -type d 2>/dev/null | head -1)
if [ -n "$LIBS_DIR" ]; then
    find "$LIBS_DIR" -name "*.dylib" -exec codesign --force --sign - {} \; || true
fi

codesign --force --deep --sign - "$BUNDLE" || true
codesign --verify --deep --strict --verbose=2 "$BUNDLE" || echo "WARNING: verify failed"

# ----- 5. Done -----------------------------------------------------------
echo ""
echo "[3/3] Done!"
echo ""
echo "Your app is at:"
echo "    dist/Convertor.app"
echo ""
echo "To zip it:"
echo "    ditto -c -k --sequesterRsrc --keepParent dist/Convertor.app Convertor-mac.zip"
echo ""
echo "First launch on another Mac needs:"
echo "    right-click -> Open -> Open"
echo "  or if 'damaged':"
echo "    xattr -cr /Applications/Convertor.app"
echo ""