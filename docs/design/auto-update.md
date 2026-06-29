# Auto-Update Design — simple-edge-tts

> **Status:** design-only (#172). Implementation deferred until the self-update
> mechanism is built. This document serves as a reference for future work.

## 1. Current State

The app detects new releases via the GitHub Releases API and shows a toast
notification. The user can click "Download" to open the release page in a
browser, or "Skip" to suppress notifications for that version.

- **Detection:** `src/update_checker.py` compares the installed version against
  the latest GitHub Release tag.
- **Notification:** Toast with action buttons (since #171).
- **Preferences:** Settings toggle for auto-check, skip-version persistence
  (since #170).
- **Limitations:** No download, no install, no self-replace. The user must
  manually download and re-install.

## 2. Strategy Options

### A. Notification-Only (Current)

Detect → notify with link to GitHub Releases. The user downloads and installs
manually.

| Pro | Con |
|-----|-----|
| Zero complexity | Friction — most users skip |
| No code signing burden | No analytics on adoption |
| Safe (no binary manipulation) | |

### B. Background Download + Notify to Install

Detect → download in background → notify with "Install & Restart" button.

| Pro | Con |
|-----|-----|
| One-click install | Must handle download failures |
| Progress feedback possible | Temp disk space (~80 MB per update) |
| User still in control | |

### C. Fully Silent Auto-Update

Detect → download → replace → restart without user interaction.

| Pro | Con |
|-----|-----|
| Zero user friction | Risky without code signing |
| Best adoption rate | May interrupt active TTS generation |
| | Requires robust rollback |

**Recommendation:** Start with **B** (background download + notify). Move to C
only after code signing and notarization are in place.

## 3. Platform Matrix

| Concern | macOS | Windows |
|---|---|---|
| **Binary format** | `.dmg` (drag-to-install) | `.zip` containing `.exe` |
| **Self-replace** | `.app` bundle can be swapped atomically | `.exe` needs a helper script (file-in-use lock) |
| **Restart mechanism** | `NSWorkspace.open(_:newInstance:)` or `/usr/bin/open -n` | Batch script: exit → replace → relaunch |
| **Signing** | Apple notarization + staple | EV Code Signing certificate |
| **Temp location** | `$TMPDIR/simple-edge-tts-update/` | `%TEMP%/simple-edge-tts-update/` |
| **Permissions** | App must be in `/Applications/` for reliable self-replace | Install dir must be user-writable |

### Linux

Out of scope for the initial implementation. Linux distribution is typically
via package managers (apt, Flatpak, AppImage), each with its own update
mechanism.

## 4. Download & Verify Flow

```
User clicks "Install & Restart"
        │
        ▼
┌─────────────────────────────┐
│ 1. Fetch release metadata   │  GET /repos/cheerc/simple-edge-tts/releases/latest
│    from GitHub API          │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 2. Select platform asset    │  Match .dmg (macOS) or .zip (Windows)
│    from release assets      │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 3. Download to temp dir     │  Stream to disk with progress callbacks
│    with progress tracking   │  Expected size: ~50-80 MB
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 4. Verify SHA256 checksum   │  Compare against SHA256SUMS.txt in release
│                             │  Abort on mismatch — do NOT execute
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 5. Extract/replace          │  See §5 per platform
└─────────────────────────────┘
```

**Progress reporting:** The download progress (bytes received / total) should
be surfaced via the system tray tooltip and/or a persistent toast. The
`download_worker.py` (to be created) would emit progress events to the
frontend via the existing pywebview IPC bridge.

**Error handling:**
- Network failure → retry up to 3 times with exponential backoff
- SHA256 mismatch → delete temp files, notify user, abort
- Disk full → notify user, suggest cleanup

## 5. Install & Restart Flow

### macOS

```
1. Mount .dmg          hdiutil attach update.dmg -nobrowse
2. Copy .app bundle    ditto /Volumes/SimpleEdgeTTS/SimpleEdgeTTS.app
                             /Applications/SimpleEdgeTTS.app.new
3. Unmount .dmg        hdiutil detach /Volumes/SimpleEdgeTTS
4. Atomic swap         mv /Applications/SimpleEdgeTTS.app
                             /Applications/SimpleEdgeTTS.app.old &&
                       mv /Applications/SimpleEdgeTTS.app.new
                             /Applications/SimpleEdgeTTS.app
5. Relaunch            open -n /Applications/SimpleEdgeTTS.app
6. Self-terminate      The old process exits after spawning the new one
7. Cleanup             rm -rf /Applications/SimpleEdgeTTS.app.old
                       (deferred — on next launch)
```

**Caveats:**
- The app must reside in `/Applications/` for `open -n` to work correctly.
  If the user runs from `~/Downloads/`, show a prompt to move to
  `/Applications/` first.
- `pywebview` macOS backend (`WKWebView`) does not survive `execve`, so a
  full process restart is required.

### Windows

```
1. Extract .zip        Expand-Archive update.zip -DestinationPath
                             %TEMP%/simple-edge-tts-update/
2. Write helper batch  %TEMP%/simple-edge-tts-update/update.bat:
                       @echo off
                       timeout /t 2 /nobreak >nul
                       move /Y "%TEMP%\simple-edge-tts-update\*.exe"
                               "<install_dir>\"
                       start "" "<install_dir>\simple-edge-tts.exe"
                       del "%~f0"
3. Launch batch        cmd /c %TEMP%/simple-edge-tts-update/update.bat
4. Self-terminate      Current process exits
```

**Caveats:**
- The `.exe` file is locked while the process runs. The helper batch script
  waits 2 seconds for the old process to fully exit before moving the new
  binary.
- Portable builds (`.exe` run from USB/arbitrary folder) replace in-place.
- Installed builds (via NSIS/MSI in the future) should update the install
  directory.

### Rollback on Failure

- **macOS:** Keep `SimpleEdgeTTS.app.old` until the new version successfully
  launches and passes a startup health check (e.g., main window created,
  pywebview loaded). If the new version crashes within 30 seconds, restore
  the old `.app` bundle and notify the user.
- **Windows:** Keep the old `.exe` as `.exe.old`. If the new process exits
  with code ≠ 0 within 30 seconds, restore.

## 6. User Experience

### Download Progress

- **System tray tooltip:** "Downloading update... 45%" (updated every 500ms).
- **Toast (optional):** Persistent toast with progress bar and "Cancel" button.
- Do NOT block the main UI — TTS generation and playback continue during
  download.

### "Install & Restart" Prompt

After download + verification succeeds:

```
┌─────────────────────────────────────────┐
│  Update Ready                            │
│                                          │
│  Version 0.2.0 is ready to install.      │
│  The app will restart to apply.          │
│                                          │
│  [Install & Restart]   [Later]           │
└─────────────────────────────────────────┘
```

- **"Install & Restart":** Executes the platform-specific install flow (§5).
- **"Later":** Dismisses the toast. The downloaded update remains in the temp
  directory. On next app launch, detect the pending update and re-prompt
  (skip re-download).

### Settings Integration

The Settings → Updates section (#170) already provides:
- **Auto-check toggle:** Disable to skip all update checks (including
  background download).
- **Manual check button:** Triggers check immediately.
- **Skip version management:** Clear skipped version to re-enable
  notifications for a previously skipped release.

Future additions when self-update is implemented:
- **Auto-download toggle:** "Automatically download updates in the background"
- **Update channel selector:** "Stable" / "Beta"

## 7. Security Considerations

- **HTTPS only:** All GitHub API calls and asset downloads must use HTTPS.
- **SHA256 verification mandatory:** Never execute or replace a binary without
  checksum verification. The SHA256SUMS.txt file itself is delivered over
  HTTPS from GitHub's trusted domain.
- **Code signing verification (future):** Once Apple notarization and Windows
  EV signing are in place, verify the signature before replacing.
- **No privilege escalation:** The updater runs as the current user. No
  `sudo`/admin prompts. On macOS, `.app` in `/Applications/` may require
  user approval for the first move — this is handled by macOS Gatekeeper,
  not our code.

## 8. Out of Scope / Future

| Item | Rationale |
|------|-----------|
| **Linux support** | Fragmented ecosystem (AppImage/Flatpak/snap/apt). Each has its own update mechanism. |
| **Delta/patch updates** | Complex diff generation; full download (~80 MB) is acceptable for a desktop app. |
| **App Store distribution** | Mac App Store and Microsoft Store have built-in update mechanisms — our custom updater would be redundant. |
| **Background service / daemon** | Over-engineering for a TTS utility. On-launch check is sufficient. |
| **Update rollout / staged %** | Needs a server-side component. GitHub Releases provides no staged-rollout capability. |
| **Forced/security updates** | Requires a minimum-version policy server. Out of scope until we have >10k users. |

## 9. Implementation Phases (Proposed)

| Phase | Scope | Effort |
|-------|-------|--------|
| **Phase 1** (#170, #171, #172) | Detection UI, toast actions, design doc | ✅ Done |
| **Phase 2** | Background download worker + progress UI | ~3 days |
| **Phase 3** | Platform install/restart (macOS first) | ~2 days |
| **Phase 4** | Windows install/restart | ~2 days |
| **Phase 5** | Rollback, edge cases, polish | ~2 days |
| **Phase 6** | Code signing + notarization | ~5 days (procurement + CI) |

## 10. References

- [#170](https://github.com/cheerc/simple-edge-tts/issues/170) — Settings auto-update preferences
- [#171](https://github.com/cheerc/simple-edge-tts/issues/171) — Toast action buttons
- [#172](https://github.com/cheerc/simple-edge-tts/issues/172) — This design doc
- [GitHub Releases API](https://docs.github.com/en/rest/releases/releases)
- [Apple Notarization](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)
