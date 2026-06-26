# Design Spec: Support single-file Windows .exe release via PyInstaller --onefile

## Goal & Background
Currently, the Windows release is bundled in `--onedir` mode, which generates a zip file containing a directory with the executable and many dependency DLLs/files.
The goal is to standardise the Windows packaging to a single-file executable (`--onefile` mode) to improve user download and installation experience.

## Open Questions & Risks
- **AV False Positives**: PyInstaller `--onefile` executables are self-extracting zip stubs, which are sometimes flagged by antivirus (AV) heuristics. Since we already use `--noupx` to avoid UPX compression, this risk is minimized but still present.
- **Logging Clutter & Permissions**: In `--onefile` mode, writing logs to the executable's directory (which might be the Desktop or Downloads) will clutter the user's files. Additionally, if the executable is placed in a read-only directory (e.g., `C:\Program Files\`), writing logs to `Path(sys.executable).parent` will raise a `PermissionError`.

## Proposed Approaches

### Approach 1: Simple `--onefile` switch
Change `--onedir` to `--onefile` for Windows in `deploy.sh` and `release.yml`. Keep log directories as-is (`Path(sys.executable).parent`).
- **Pros**: Minimal code changes.
- **Cons**: Litters Desktop/Downloads with log files. Crashes or fails to write logs if run from write-protected folders.

### Approach 2: `--onefile` with Smart Runtime Logging Fallback (Recommended)
Switch to `--onefile` on Windows. Refactor `src/logging_config.py` to check if the app is running in `--onefile` mode (by checking if `sys._MEIPASS` is outside the executable's directory) or if the executable's directory is write-protected. If either is true, write logs to `%LOCALAPPDATA%/simple-edge-tts/logs/` instead.
- **Pros**: Avoids littering user folders. Bypasses write-permission issues.
- **Cons**: Requires minor updates to `src/logging_config.py` and its tests.

### Approach 3: Switch to Nuitka
Rebuild packaging pipeline using Nuitka compilation.
- **Pros**: Reduces AV false positives.
- **Cons**: High complexity, long build times, high risk of CI integration failures.

---

## Detailed Design (Approach 2)

### 1. PyInstaller Configuration
- For Windows build in `deploy.sh` and `.github/workflows/release.yml`:
  - Change `--onedir` to `--onefile`.
  - Update packaging logic (`Compress-Archive`) to package `dist/simple-edge-tts.exe` instead of `dist/simple-edge-tts` folder.
  - Update display path to `dist/simple-edge-tts.exe` in `deploy.sh`.

### 2. Logging Path Resolution (`src/logging_config.py`)
- Detect `--onefile` mode at runtime:
  ```python
  exe_dir = Path(sys.executable).parent
  try:
      meipass = Path(sys._MEIPASS)
      is_onefile = not meipass.is_relative_to(exe_dir)
  except Exception:
      is_onefile = True
  ```
- Detect directory writability by attempting to touch/unlink a temporary file.
- If `is_onefile` is True or directory is not writable, write logs to `%LOCALAPPDATA%/simple-edge-tts/logs/`.
- Otherwise (for `--onedir` portable folder execution), write logs to `exe_dir`.

### 3. Unit Tests (`tests/test_logging_config.py`)
- Update `test_windows_frozen_log_dir` to mock `sys._MEIPASS` as inside `sys.executable` and test write-ability to assert that `--onedir` returns `exe_dir`.
- Add `test_windows_onefile_log_dir` to mock `sys._MEIPASS` as outside `sys.executable` and assert that it falls back to `%LOCALAPPDATA%`.
- Add `test_windows_onedir_readonly_fallback` to mock a read-only `--onedir` folder and assert that it falls back to `%LOCALAPPDATA%`.
