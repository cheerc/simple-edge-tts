#!/usr/bin/env bash
set -euo pipefail

# deploy.sh — PyInstaller packaging script for simple-edge-tts
# Usage: ./deploy.sh [build|clean|build-exe|get-exe]

APP_NAME="simple-edge-tts"
ENTRY_POINT="src/main.py"
RESOURCES_DIR="src/resources"
REPO="cheerc/simple-edge-tts"

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

    # Build frontend assets
    info "Building frontend..."
    (cd frontend && npm run build) || fail "Frontend build"
    pass "Frontend build"

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
        --add-data "src/static${sep}src/static"
        --add-data "frontend/dist${sep}frontend/dist"
        --hidden-import pystray
        --hidden-import PIL
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
            # Ref: #66 — Stage .app + Applications symlink for drag-to-install DMG.
            # hdiutil -srcfolder must point at a folder containing the .app
            # (not the PyInstaller onedir folder, which lacks .app structure).
            local staging="dist/dmg-staging"
            rm -rf "$staging"
            mkdir -p "$staging"
            cp -R "$app_path" "$staging/"
            ln -s /Applications "$staging/Applications"

            if hdiutil create -volname "$APP_NAME" -srcfolder "$staging" \
                -ov -format UDZO "$dmg_path" 2>/dev/null; then
                pass ".dmg created: ${dmg_path}"
            else
                echo -e "${RED}⚠ Warning${RESET}: .dmg creation failed (non-fatal)"
            fi
            rm -rf "$staging"
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

# Ref: #85 — Ensure gh CLI is installed and authenticated before CI commands.
check_gh() {
    if ! command -v gh &>/dev/null; then
        fail "GitHub CLI (gh) is not installed. Install from https://cli.github.com"
    fi
    if ! gh auth status &>/dev/null 2>&1; then
        fail "GitHub CLI is not authenticated. Run 'gh auth login' first"
    fi
}

do_build_exe() {
    check_gh

    info "Triggering CI build via workflow_dispatch..."
    if ! gh workflow run release.yml --repo "$REPO"; then
        fail "Failed to trigger workflow. Check your permissions and repo access"
    fi
    pass "Workflow triggered"

    # Wait a moment for the run to register
    sleep 3

    info "Waiting for CI build to complete..."
    # Find the most recent workflow_dispatch run
    local run_id
    run_id=$(gh run list --repo "$REPO" --workflow=release.yml --event=workflow_dispatch --limit=1 --json databaseId --jq '.[0].databaseId')
    if [ -z "$run_id" ] || [ "$run_id" = "null" ]; then
        fail "Could not find the triggered workflow run"
    fi

    echo "  Run ID: ${run_id}"
    echo "  URL: https://github.com/${REPO}/actions/runs/${run_id}"

    if gh run watch "$run_id" --repo "$REPO" --exit-status; then
        pass "CI build completed successfully (run ${run_id})"
    else
        fail "CI build failed (run ${run_id}). Check: https://github.com/${REPO}/actions/runs/${run_id}"
    fi
}

do_get_exe() {
    check_gh

    info "Finding latest successful workflow_dispatch build..."
    local run_id
    run_id=$(gh run list --repo "$REPO" --workflow=release.yml --event=workflow_dispatch --status=success --limit=1 --json databaseId --jq '.[0].databaseId')
    if [ -z "$run_id" ] || [ "$run_id" = "null" ]; then
        fail "No successful workflow_dispatch runs found. Run './deploy.sh build-exe' first"
    fi

    echo "  Run ID: ${run_id}"

    info "Downloading Windows artifact..."
    mkdir -p dist
    if gh run download "$run_id" --repo "$REPO" -n "${APP_NAME}-Windows" --dir dist/; then
        pass "Windows artifact downloaded to dist/"
        # List downloaded files
        find dist/ -type f -name "*.zip" -o -name "*.exe" | while read -r f; do
            echo "  → $f"
        done
    else
        fail "Failed to download Windows artifact from run ${run_id}"
    fi
}

case "$CMD" in
    build)
        do_build
        ;;
    clean)
        do_clean
        ;;
    build-exe)
        do_build_exe
        ;;
    get-exe)
        do_get_exe
        ;;
    *)
        echo "Usage: $0 [build|clean|build-exe|get-exe]"
        exit 1
        ;;
esac
