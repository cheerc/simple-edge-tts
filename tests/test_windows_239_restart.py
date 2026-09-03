"""Test #239 — Windows verified replacement now reliably auto-restarts.

Field: G:\\... shared Downloads with spaces, old became new but no
auto-restart (bat had no telemetry, start without /d, no start errorlevel
gate, and del timing could truncate). Fix must:
- log every copy/fc/start errorlevel to bat.log
- use start "" /d "<exe_dir>" "<exe>" with quoted dir for spaces/UNC
- gate start errorlevel and write update-failed.flag with code
- use (goto) 2>nul & del "%~f0" for reliable self-delete
- keep #202 _MEIPASS scrub and #236 copy/fc gates
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.update_manager import UpdateManager


CREATE_NO_WINDOW = 0x08000000


def _make_mgr(new_exe: str):
    mgr = UpdateManager(current_version="0.1.8")
    mgr._windows_new_exe = Path(new_exe)
    return mgr


def _get_bat_content(mgr, old_exe: str) -> str:
    with patch("sys.platform", "win32"), \
         patch("subprocess.CREATE_NO_WINDOW", CREATE_NO_WINDOW, create=True), \
         patch("subprocess.Popen"), \
         patch("pathlib.Path.write_text") as mock_write, \
         patch("src.update_manager.UpdateManager._install_cleanup"), \
         patch("sys.executable", old_exe):
        with pytest.raises(SystemExit):
            mgr._windows_restart()
    return mock_write.call_args.args[0]


class TestWindows239TelemetryAndReliableRelaunch:
    def test_bat_has_log_and_reports_each_step(self):
        mgr = _make_mgr(r"C:\temp\new\simple-edge-tts.exe")
        bat = _get_bat_content(mgr, r"C:\Users\u\simple-edge-tts.exe")
        assert 'set "LOG=' in bat
        assert 'bat.log' in bat
        # Every major step logs to LOG
        for marker in ["copy /Y", 'fc /b', 'start ""']:
            assert marker.lower() in bat.lower()
            # step must log to LOG
            idx = bat.lower().index(marker.lower())
            # nearby should have >> "%LOG%"
            snippet = bat[max(0, idx-200): idx+500]
            assert '%LOG%' in snippet, f"{marker} not logging to LOG: {snippet[:200]}"
        # errorlevel for each gate must be logged
        assert bat.lower().count("errorlevel") >= 3  # copy, fc, start

    def test_start_uses_d_and_quoted_dir_for_spaces(self):
        # Path with spaces: Program Files
        old = r"C:\Program Files\Simple Edge TTS\simple-edge-tts.exe"
        new = r"C:\Users\u\Downloads\simple-edge-tts-new.exe"
        mgr = _make_mgr(new)
        bat = _get_bat_content(mgr, old)
        # Must use /d with quoted parent dir
        assert 'start "" /d "' in bat
        # Parent dir quoted
        assert r'"C:\Program Files\Simple Edge TTS"' in bat
        # old_exe itself quoted
        assert f'"{old}"' in bat
        # start errorlevel gate
        start_idx = bat.index('start "" /d')
        tail = bat[start_idx: start_idx+500]
        assert "errorlevel" in tail.lower()
        assert "update launch failed" in tail

    def test_unc_like_shared_path_quoted(self):
        # Simulate shared drive G:\ with space
        old = r"G:\Shared Downloads\Simple Edge TTS\simple-edge-tts.exe"
        new = r"C:\temp\new\simple-edge-tts.exe"
        mgr = _make_mgr(new)
        bat = _get_bat_content(mgr, old)
        assert f'"{old}"' in bat
        assert f'"{new}"' in bat
        assert 'start "" /d "' in bat
        assert r'"G:\Shared Downloads\Simple Edge TTS"' in bat

    def test_fail_markers_include_errorlevel(self):
        mgr = _make_mgr(r"C:\temp\new\simple-edge-tts.exe")
        bat = _get_bat_content(mgr, r"C:\Users\u\simple-edge-tts.exe")
        # All three fail markers should include errorlevel=%errorlevel%
        assert bat.count("update replace failed errorlevel=%errorlevel%") == 1
        assert bat.count("update verify failed errorlevel=%errorlevel%") == 1
        assert bat.count("update launch failed errorlevel=%errorlevel%") == 1

    def test_self_delete_uses_goto_pattern(self):
        mgr = _make_mgr(r"C:\temp\new\simple-edge-tts.exe")
        bat = _get_bat_content(mgr, r"C:\Users\u\simple-edge-tts.exe")
        assert '(goto) 2>nul & del "%~f0"' in bat
        # old plain del should not be the final line alone
        assert bat.strip().endswith('(goto) 2>nul & del "%~f0"')

    def test_copy_and_fc_still_gated_before_start(self):
        mgr = _make_mgr(r"C:\temp\new\simple-edge-tts.exe")
        bat = _get_bat_content(mgr, r"C:\Users\u\simple-edge-tts.exe")
        lower = bat.lower()
        copy_idx = lower.index("copy /y")
        fc_idx = lower.index("fc /b")
        start_idx = lower.index('start ""')
        assert copy_idx < fc_idx < start_idx
        # Each gate still writes update-failed.flag
        assert lower.count("update-failed.flag") >= 3

    def test_meipass_reset_still_before_start(self):
        mgr = _make_mgr(r"C:\temp\new\simple-edge-tts.exe")
        bat = _get_bat_content(mgr, r"C:\Users\u\simple-edge-tts.exe")
        assert "set _MEIPASS=" in bat
        assert "set PYINSTALLER_RESET_ENVIRONMENT=1" in bat
        meipass_idx = bat.index("set _MEIPASS=")
        start_idx = bat.index('start ""')
        assert meipass_idx < start_idx

    def test_bat_logs_to_log_file_with_2and1(self):
        mgr = _make_mgr(r"C:\temp\new\simple-edge-tts.exe")
        bat = _get_bat_content(mgr, r"C:\Users\u\simple-edge-tts.exe")
        # Redirection 2>&1 ensures stderr captured
        assert '>> "%LOG%" 2>&1' in bat

    def test_timeout_preserved(self):
        mgr = _make_mgr(r"C:\temp\new\simple-edge-tts.exe")
        bat = _get_bat_content(mgr, r"C:\Users\u\simple-edge-tts.exe")
        assert "timeout /t 2 /nobreak" in bat
