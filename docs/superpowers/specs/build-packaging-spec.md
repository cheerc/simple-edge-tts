# Build Packaging Spec

## Overview
simple-edge-tts uses PyInstaller for cross-platform desktop app packaging.
macOS produces `.app` bundle + `.dmg`; Windows produces a single-file `.exe`.

## Platform Build Matrix

| Platform | PyInstaller Mode | Output | CI Workflow |
|----------|-----------------|--------|-------------|
| macOS | `--onedir` | `dist/simple-edge-tts.app` + `dist/simple-edge-tts.dmg` | `release.yml` (tag `v*`) |
| Windows | `--onefile` | `dist/simple-edge-tts.exe` → zipped | `release.yml` (tag `v*`) |

## Build Entry Points

### Local

- `./deploy.sh build` — full macOS build (`.app` + `.dmg`)
- `./deploy.sh build-exe` — trigger CI Windows build, wait for completion, download artifact
- `./deploy.sh clean` — remove build artifacts + stale `.spec` files

### CI

- `.github/workflows/release.yml` triggers on tag `v*`
- Matrix: macOS (arm64) + Windows (x64)
- Conditional `--onefile`/`--onedir` based on `matrix.platform`

## Key Constraints

- Windows `--onefile` extracts to temp dir at runtime (`sys._MEIPASS`)
  → config/log files must use writable path (see `config-persistence-spec`)
- Windows artifact: `dist/simple-edge-tts.exe` zipped as `dist/simple-edge-tts-windows.zip`
- macOS artifact: `dist/simple-edge-tts.app` bundled into `dist/simple-edge-tts.dmg`
- `build-exe` auto-downloads artifact after CI completion; cleans existing `.zip` to prevent extraction conflicts

## Related

- PR #107: feat(build/settings)
- Issues: #106 (onefile), #104 (build-exe merge)
