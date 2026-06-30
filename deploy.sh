#!/usr/bin/env bash
set -euo pipefail

# deploy.sh — PyInstaller packaging script for simple-edge-tts
# Usage: ./deploy.sh [build|clean|build-exe]

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

# Ref: #175 — Build .app, launch, check runtime log for errors.
do_verify() {
    detect_platform

    if [ "$PLATFORM" != "macOS" ]; then
        echo "⚠ verify currently only supports macOS"
        exit 0
    fi

    # 1. Build
    info "Building .app for verification..."
    do_build

    # 2. Find previous log count to identify new log file
    local log_dir="$HOME/Library/Logs/simple-edge-tts"
    local prev_count
    prev_count=$(ls -1 "$log_dir"/*.log 2>/dev/null | wc -l || echo 0)

    # 3. Launch app (background, wait for startup)
    info "Launching .app..."
    open "dist/${APP_NAME}.app"

    # 4. Wait for app startup + initial API calls (8 seconds)
    echo "Waiting for app startup (8s)..."
    sleep 8

    # 5. Read log — prefer new file, fallback to latest
    local log_file
    local new_count
    new_count=$(ls -1 "$log_dir"/*.log 2>/dev/null | wc -l || echo 0)
    if [ "$new_count" -gt "$prev_count" ]; then
        log_file=$(ls -t "$log_dir"/*.log | head -1)
    else
        log_file=$(ls -t "$log_dir"/*.log 2>/dev/null | head -1)
    fi

    if [ -z "$log_file" ] || [ ! -f "$log_file" ]; then
        echo "⚠ No log file found at $log_dir"
        pkill -f "${APP_NAME}" 2>/dev/null || true
        exit 1
    fi

    info "Checking log: $(basename "$log_file")"

    # 6. Grep for errors
    local errors
    errors=$(grep -iE 'ERROR|exception|Traceback' "$log_file" || true)

    # 7. Kill app
    pkill -f "${APP_NAME}" 2>/dev/null || true

    # 8. Report
    if [ -n "$errors" ]; then
        echo ""
        echo "========== BUILD VERIFICATION FAILED =========="
        echo "Errors found in runtime log:"
        echo "$errors"
        echo "================================================"
        exit 1
    fi

    pass "Build verification — log clean, no errors detected"
}

# Ref: #90 — Extract version from pyproject.toml (single source of truth).
get_version() {
    python3 -c "import re; print(re.search(r'version\s*=\s*\"([^\"]+)\"', open('pyproject.toml').read()).group(1))"
}

do_build() {
    detect_platform

    local sep
    sep=$(get_path_sep)

    # Ref: #90 — Read version once, use for all platform-specific embedding.
    local VERSION
    VERSION=$(get_version)
    info "Version: ${VERSION} (from pyproject.toml)"

    # Build frontend assets
    # Ref: #160 — npm ci ensures node_modules matches lockfile before build.
    info "Installing frontend dependencies..."
    (cd frontend && npm ci) || fail "Frontend npm ci"
    info "Building frontend..."
    (cd frontend && npm run build) || fail "Frontend build"
    pass "Frontend build"

    # Clean previous build
    info "Cleaning previous build..."
    rm -rf build/ dist/

    # Build with PyInstaller
    info "Building ${APP_NAME} with PyInstaller..."

    local dir_mode="--onedir"
    if [ "$PLATFORM" = "Windows" ]; then
        dir_mode="--onefile"
    fi

    local pyinstaller_args=(
        --name "$APP_NAME"
        --windowed
        "$dir_mode"
        --noupx
        --add-data "${RESOURCES_DIR}${sep}${RESOURCES_DIR}"
        --add-data "src/static${sep}src/static"
        --add-data "frontend/dist${sep}frontend/dist"
        --add-data "pyproject.toml${sep}."
        --hidden-import pystray
        --hidden-import PIL
        --hidden-import edge_tts
        --noconfirm
        "$ENTRY_POINT"
    )

    # Ref: #90 — Windows .exe version metadata via --version-file (VSVersionInfo).
    # PyInstaller does not support --file-version/--product-version; must use --version-file.
    if [ "$PLATFORM" = "Windows" ]; then
        local major minor patch
        IFS='.' read -r major minor patch <<< "$VERSION"
        sed -e "s/__MAJOR__/${major}/g" \
            -e "s/__MINOR__/${minor}/g" \
            -e "s/__PATCH__/${patch}/g" \
            -e "s/__VERSION__/${VERSION}/g" \
            version_info.template > version_info.txt
        pyinstaller_args+=(--version-file version_info.txt)
        pass "Generated version_info.txt (v${VERSION})"
    fi

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

    # Ref: #90 — Patch macOS .app Info.plist with correct version from pyproject.toml.
    if [ "$PLATFORM" = "macOS" ] && [ -d "dist/${APP_NAME}.app" ]; then
        info "Patching Info.plist version → ${VERSION}..."
        plutil -replace CFBundleShortVersionString -string "$VERSION" "dist/${APP_NAME}.app/Contents/Info.plist"
        plutil -replace CFBundleVersion -string "$VERSION" "dist/${APP_NAME}.app/Contents/Info.plist"
        pass "Info.plist version set to ${VERSION}"
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

        # Ref: #198 — Create macOS ZIP for direct download (browser quarantine
        # propagation is more predictable with ZIP than DMG).
        info "Creating macOS ZIP..."
        if ditto -c -k --sequesterRsrc --keepParent "$app_path" "dist/${APP_NAME}-macos.zip" 2>/dev/null; then
            pass ".zip created: dist/${APP_NAME}-macos.zip"
        else
            echo -e "${RED}⚠ Warning${RESET}: .zip creation failed (non-fatal)"
        fi

        # Ref: #90 — Clean raw PyInstaller onedir output; only .app + .dmg needed.
        if [ -d "dist/${APP_NAME}" ]; then
            rm -rf "dist/${APP_NAME}"
            pass "Cleaned raw onedir output (dist/${APP_NAME}/)"
        fi
    fi

    # Summary
    echo
    info "Build complete! (v${VERSION})"
    if [ "$PLATFORM" = "macOS" ]; then
        echo "  App: dist/${APP_NAME}.app"
        echo "  DMG: dist/${APP_NAME}.dmg"
        echo "  ZIP: dist/${APP_NAME}-macos.zip"
    elif [ "$PLATFORM" = "Windows" ]; then
        echo "  Exe: dist/${APP_NAME}.exe"
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

    local branch
    branch=$(git branch --show-current 2>/dev/null || echo "main")
    if [ -z "$branch" ]; then
        branch="main"
    fi

    info "Triggering CI build via workflow_dispatch on branch ${branch}..."
    if ! gh workflow run release.yml --ref "$branch" --repo "$REPO"; then
        fail "Failed to trigger workflow. Check your permissions and repo access"
    fi
    pass "Workflow triggered on branch ${branch}"

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

        info "Downloading Windows artifact..."
        mkdir -p dist
        # Ref: #104 — Clean up existing download target files to prevent extraction failure
        rm -f dist/simple-edge-tts-windows.zip
        if gh run download "$run_id" --repo "$REPO" -n "${APP_NAME}-Windows" --dir dist/; then
            pass "Windows artifact downloaded to dist/"
            # List downloaded files
            find dist/ -type f -name "*.zip" -o -name "*.exe" | while read -r f; do
                echo "  → $f"
            done
        else
            fail "Failed to download Windows artifact from run ${run_id}"
        fi
    else
        fail "CI build failed (run ${run_id}). Check: https://github.com/${REPO}/actions/runs/${run_id}"
    fi
}

case "$CMD" in
    build)
        do_build
        ;;
    clean)
        do_clean
        ;;
    verify)
        do_verify
        ;;
    build-exe)
        do_build_exe
        ;;
    *)
        echo "Usage: $0 [build|clean|verify|build-exe]"
        exit 1
        ;;
esac
