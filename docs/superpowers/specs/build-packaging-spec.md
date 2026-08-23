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
- **Bundle alignment contract**: `deploy.sh` and `.github/workflows/release.yml` each carry their own PyInstaller `--add-data` / `--hidden-import` list — any packaging change must be applied to **both**, they are not shared. `pyproject.toml` is a required bundle item: frozen builds fall back to reading it for version resolution when importlib.metadata is unavailable (Ref #174/#215).
  - Carrier difference: `deploy.sh` uses a bash array, so comments may appear between items freely; `release.yml` uses backslash continuation lines — a comment line inside the chain terminates the command and turns every later line into a standalone command (exit 127). Keep comments outside the chain.

## Related

- Release 操作步驟（version bump / PR / tag / 驗證）: [release-process-spec.md](release-process-spec.md)
- PR #107: feat(build/settings)
- Issues: #106 (onefile), #104 (build-exe merge)
