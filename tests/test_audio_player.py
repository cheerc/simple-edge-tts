"""Tests for audio_player — state machine: idle→playing→idle, stop, errors."""

from unittest.mock import patch
from src.audio_player import AudioPlayer, PlayerState


class TestPlayerState:
    def test_initial_state_is_idle(self):
        player = AudioPlayer()
        assert player.state == PlayerState.IDLE

    def test_play_changes_state(self):
        player = AudioPlayer()
        with patch.object(player, "_media_player", create=True), \
             patch("src.audio_player.Path.exists", return_value=True):
            player.play("/fake/path.mp3")
            assert player.state == PlayerState.PLAYING

    def test_stop_returns_to_idle(self):
        player = AudioPlayer()
        with patch.object(player, "_media_player", create=True), \
             patch("src.audio_player.Path.exists", return_value=True):
            player.play("/fake/path.mp3")
            player.stop()
            assert player.state == PlayerState.IDLE

    def test_stop_when_idle_is_noop(self):
        player = AudioPlayer()
        player.stop()
        assert player.state == PlayerState.IDLE

    def test_play_nonexistent_file_stays_idle(self):
        player = AudioPlayer()
        player.play("/nonexistent/file.mp3")
        assert player.state == PlayerState.IDLE
