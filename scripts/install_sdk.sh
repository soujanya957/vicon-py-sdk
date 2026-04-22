#!/usr/bin/env bash
# install_sdk.sh — copy the Vicon DataStream C SDK library into the package
#
# After running this, `import vicon_sdk` will find the library automatically
# without needing VICON_SDK_PATH.
#
# Usage:
#   bash scripts/install_sdk.sh                  # auto-detect from common paths
#   bash scripts/install_sdk.sh /path/to/Mac     # explicit SDK directory
#
# Download the SDK from:
#   https://www.vicon.com/software/datastream-sdk/

set -e

DEST="$(dirname "$0")/../vicon_sdk"

# ── Accept an explicit path ────────────────────────────────────────────────
if [ -n "$1" ]; then
    SRC_DIR="$1"
    if [ ! -d "$SRC_DIR" ]; then
        echo "ERROR: Directory not found: $SRC_DIR"
        exit 1
    fi
else
    # ── Auto-detect common download locations ──────────────────────────────
    SRC_DIR=""
    CANDIDATES=(
        "$HOME/Downloads"/ViconDataStreamSDK_*/*/Mac
        "$HOME/Downloads"/ViconDataStreamSDK_*/*/*/Mac
        "$HOME/Downloads"/ViconDataStreamSDK_*/Linux64
        "."
    )
    for c in "${CANDIDATES[@]}"; do
        for expanded in $c; do
            if [ -f "$expanded/libViconDataStreamSDK_C.dylib" ] || \
               [ -f "$expanded/libViconDataStreamSDK_C.so" ] || \
               [ -f "$expanded/ViconDataStreamSDK_C.dll" ]; then
                SRC_DIR="$expanded"
                break 2
            fi
        done
    done

    if [ -z "$SRC_DIR" ]; then
        echo ""
        echo "ERROR: Could not find the Vicon DataStream SDK."
        echo ""
        echo "Download it from:"
        echo "  https://www.vicon.com/software/datastream-sdk/"
        echo ""
        echo "Then run:"
        echo "  bash scripts/install_sdk.sh /path/to/Mac"
        echo ""
        echo "  macOS  → .../ViconDataStreamSDK_x.x.x.../Mac"
        echo "  Linux  → .../ViconDataStreamSDK_x.x.x.../Linux64"
        exit 1
    fi
fi

# ── Detect platform and pick library name ─────────────────────────────────
UNAME="$(uname -s)"
case "$UNAME" in
    Darwin*)            LIB="libViconDataStreamSDK_C.dylib" ;;
    Linux*)             LIB="libViconDataStreamSDK_C.so"    ;;
    MINGW*|CYGWIN*|MSYS*) LIB="ViconDataStreamSDK_C.dll"   ;;
    *)
        echo "ERROR: Unsupported platform: $UNAME"
        exit 1
        ;;
esac

SRC="$SRC_DIR/$LIB"
if [ ! -f "$SRC" ]; then
    echo "ERROR: $LIB not found in $SRC_DIR"
    ls "$SRC_DIR" 2>/dev/null
    exit 1
fi

# ── Copy all shared libraries (C lib depends on CPP lib at runtime) ────────
case "$UNAME" in
    Darwin*)   GLOB="*.dylib" ;;
    Linux*)    GLOB="*.so*"   ;;
    *)         GLOB="*.dll"   ;;
esac

copied=0
for f in "$SRC_DIR"/$GLOB; do
    [ -f "$f" ] || continue
    cp "$f" "$DEST/"
    echo "Installed: $f"
    copied=$((copied + 1))
done

if [ "$copied" -eq 0 ]; then
    echo "ERROR: No shared libraries found in $SRC_DIR"
    exit 1
fi

echo ""
echo "Copied $copied file(s) to $DEST"
echo ""
echo "You're all set. Test it:"
echo "  python -c \"from vicon_sdk import ViconClient; print('OK')\""
echo ""
