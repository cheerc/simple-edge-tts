#!/usr/bin/env bash
set -euo pipefail

# deploy.sh — PyInstaller packaging script for simple-edge-tts
# Usage: ./deploy.sh [build|clean]

APP_NAME="simple-edge-tts"
ENTRY_POINT="src/main.py"
RESOURCES_DIR="src/resources"

# Color output if tty
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    BOLD='\033[1m'
    RESET='\033[0m'
else
    GREEN=''
    RED=''
    BOLD=''
    RESET=''
fi

info() {
    echo -e "${BOLD}▶ $1${RESET}"
}

pass() {
    echo -e "${GREEN}✓ PASS${RESET}: $1"
}

fail() {
    echo -e "${RED}✗ FAIL${RESET}: $1"
    exit 1
}

# Platform detection
detect_platform() {
    case "$(uname -s)" in
        Darwin)  PLATFORM="macOS" ;;
        Linux)   PLATFORM="Linux" ;;
        MINGW*|MSYS*|CYGWIN*)  PLATFORM="Windows" ;;
        *)       PLATFORM="Unknown" ;;
    esac
    echo -e "Platform: ${BOLD}${PLATFORM}${RESET}"
}

# Resource path separator: : on macOS/Linux, ; on Windows
get_path_sep() {
    if [ "$PLATFORM" = "Windows" ]; then
        echo ";"
    else
        echo ":"
    fi
}

do_clean() {
    info "Cleaning build artifacts..."
    rm -rf build/ dist/ *.spec
    pass "Clean complete"
}

do_build() {
    detect_platform

    local sep
    sep=$(get_path_sep)

    # Clean previous build
    info "Cleaning previous build..."
    rm -rf build/ dist/

    # Build with PyInstaller
    info "Building ${APP_NAME} with PyInstaller..."

    local pyinstaller_args=(
        --name "$APP_NAME"
        --windowed
        --onedir
        --add-data "${RESOURCES_DIR}${sep}${RESOURCES_DIR}"
        --hidden-import PySide6
        --hidden-import edge_tts
        --noconfirm
        "$ENTRY_POINT"
    )

    # Add macOS-specific icon if available
    local icon_path="${RESOURCES_DIR}/icons/icon.icns"
    if [ -f "$icon_path" ] && [ "$PLATFORM" = "macOS" ]; then
        pyinstaller_args+=(--icon "$icon_path")
    fi

    # Add Windows-specific icon if available
    local ico_path="${RESOURCES_DIR}/icons/icon.ico"
    if [ -f "$ico_path" ] && [ "$PLATFORM" = "Windows" ]; then
        pyinstaller_args+=(--icon "$ico_path")
    fi

    if uv run pyinstaller "${pyinstaller_args[@]}"; then
        pass "PyInstaller build"
    else
        fail "PyInstaller build"
    fi

    # Post-build: macOS .dmg creation (optional)
    if [ "$PLATFORM" = "macOS" ] && command -v hdiutil &>/dev/null; then
        info "Creating .dmg..."
        local app_path="dist/${APP_NAME}.app"
        local dmg_path="dist/${APP_NAME}.dmg"

        if [ -d "$app_path" ]; then
            if hdiutil create -volname "$APP_NAME" -srcfolder "dist/${APP_NAME}" \
                -ov -format UDZO "$dmg_path" 2>/dev/null; then
                pass ".dmg created: ${dmg_path}"
            else
                echo -e "${RED}⚠ Warning${RESET}: .dmg creation failed (non-fatal)"
            fi
        fi
    fi

    # Summary
    echo
    info "Build complete!"
    echo "  Output: dist/${APP_NAME}/"
    if [ "$PLATFORM" = "macOS" ]; then
        echo "  App:    dist/${APP_NAME}/${APP_NAME}.app (if --onedir)"
    elif [ "$PLATFORM" = "Windows" ]; then
        echo "  Exe:    dist/${APP_NAME}/${APP_NAME}.exe"
    else
        echo "  Binary: dist/${APP_NAME}/${APP_NAME}"
    fi
}

CMD="${1:-build}"

case "$CMD" in
    build)
        do_build
        ;;
    clean)
        do_clean
        ;;
    *)
        echo "Usage: $0 [build|clean]"
        exit 1
        ;;
esac
