import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1] / "moonlight-voice"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from moonlight_voice.config import ServiceConfig
from moonlight_voice.server import (
    MoonlightVoiceIngressServer,
    MoonlightVoiceServer,
    _describe_tts_payload,
    _format_debug_body,
    _transcode_audio,
    load_audio_files,
)

MP3_BYTES = b"ID3\x04\x00\x00\x00\x00\x00\x00"
WAV_BYTES = b"RIFF\x24\x00\x00\x00WAVEfmt "


class ServerAudioLoadTest(unittest.TestCase):
    def test_ingress_server_delegates_to_configured_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            config = ServiceConfig(port=9000, output_file=str(base / "default.mp3"))
            audio_cache, files, audio_dir = load_audio_files(config)
            backend = MoonlightVoiceServer(("localhost", 0), config, audio_cache, files, audio_dir)
            ingress = MoonlightVoiceIngressServer(("localhost", 0), backend)
            try:
                self.assertIs(ingress.config, backend.config)
                self.assertEqual(ingress.describe_config()["port"], 9000)
            finally:
                ingress.server_close()
                backend.server_close()

    def test_load_audio_files_supports_multiple_formats(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            mp3 = base / "sample.mp3"
            wav = base / "sample.wav"
            mp3.write_bytes(b"mp3data")
            wav.write_bytes(b"wavdata")

            cfg = ServiceConfig(output_file=str(mp3), output_format="mp3")
            audio, files, audio_dir = load_audio_files(cfg)
            self.assertEqual(audio["mp3"], b"mp3data")
            self.assertEqual(files["mp3"], str(mp3))
            self.assertEqual(audio_dir, base)

            cfg2 = ServiceConfig(output_file=str(wav), output_format="wav")
            audio2, files2, audio_dir2 = load_audio_files(cfg2)
            self.assertEqual(audio2["wav"], b"wavdata")
            self.assertEqual(files2["wav"], str(wav))
            self.assertEqual(audio_dir2, base)

    def test_set_audio_stays_in_directory_and_deletes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            cfg = ServiceConfig(output_file=str(base / "default.mp3"), output_format="mp3")
            audio_cache, files, audio_dir = load_audio_files(cfg)
            server = MoonlightVoiceServer(("localhost", 0), cfg, audio_cache, files, audio_dir)
            try:
                result = server.set_audio("mp3", MP3_BYTES, "test.mp3")
                self.assertTrue(result.saved_path.exists())
                self.assertEqual(server.active_files["mp3"], str(result.saved_path))
                self.assertEqual(server.audio_cache["mp3"], MP3_BYTES)

                escaped = server.set_audio("mp3", MP3_BYTES, "../escape.mp3")
                self.assertTrue(escaped.saved_path.is_file())
                self.assertEqual(escaped.saved_path.parent, audio_dir.resolve())

                removed = server.delete_audio("mp3")
                self.assertTrue(removed)
                self.assertNotIn("mp3", server.audio_cache)
            finally:
                server.server_close()

    def test_set_audio_normalizes_extension_and_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            cfg = ServiceConfig(output_file=str(base / "default.mp3"), output_format="mp3")
            audio_cache, files, audio_dir = load_audio_files(cfg)
            server = MoonlightVoiceServer(("localhost", 0), cfg, audio_cache, files, audio_dir)
            try:
                result = server.set_audio("mp3", MP3_BYTES, "custom.invalid")
                self.assertEqual(result.normalized_filename, "default.mp3")
                self.assertTrue(result.renamed)
                self.assertTrue((audio_dir / "default.mp3").exists())
            finally:
                server.server_close()

    def test_clear_storage_removes_default_and_response_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            cfg = ServiceConfig(output_file=str(base / "default.mp3"), output_format="mp3")
            audio_cache, files, audio_dir = load_audio_files(cfg)
            server = MoonlightVoiceServer(("localhost", 0), cfg, audio_cache, files, audio_dir)
            try:
                server.set_audio("mp3", MP3_BYTES, "default.mp3")
                server.response_library.converter = lambda data, source_format, target_format: (
                    None,
                    "conversion unavailable",
                )
                server.response_library.store_audio(
                    "doorbell", MP3_BYTES, "doorbell.mp3", "audio/mpeg"
                )

                result = server.clear_storage()

                self.assertTrue(result["default_audio_deleted"])
                self.assertEqual(result["responses"]["deleted"], 1)
                self.assertFalse(server.active_files)
                self.assertFalse(server.response_library.entries)
            finally:
                server.server_close()

    @patch("moonlight_voice.server._transcode_audio", return_value=(b"converted-mp3", None))
    def test_set_audio_auto_converts_other_format(self, mock_transcode) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            cfg = ServiceConfig(output_file=str(base / "default.mp3"), output_format="mp3")
            audio_cache, files, audio_dir = load_audio_files(cfg)
            server = MoonlightVoiceServer(("localhost", 0), cfg, audio_cache, files, audio_dir)
            try:
                saved = server.set_audio("wav", WAV_BYTES, "clip.wav")
                self.assertTrue(saved.saved_path.exists())
                self.assertIn("wav", server.audio_cache)
                self.assertIn("mp3", server.audio_cache)
                self.assertEqual(server.audio_cache["mp3"], b"converted-mp3")
                self.assertTrue(Path(server.active_files["mp3"]).exists())
                self.assertEqual(cfg.output_file, server.active_files["mp3"])
                self.assertEqual(mock_transcode.call_count, 1)
            finally:
                server.server_close()

    def test_set_audio_rejects_invalid_content_before_replacing_active_clip(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            cfg = ServiceConfig(output_file=str(base / "default.mp3"), output_format="mp3")
            audio_cache, files, audio_dir = load_audio_files(cfg)
            server = MoonlightVoiceServer(("localhost", 0), cfg, audio_cache, files, audio_dir)
            try:
                server.set_audio("mp3", MP3_BYTES, "default.mp3")
                with self.assertRaisesRegex(RuntimeError, "recognizable MP3"):
                    server.set_audio("mp3", b"not audio", "replacement.mp3")
                self.assertEqual(server.audio_cache["mp3"], MP3_BYTES)
            finally:
                server.server_close()

    def test_webui_settings_are_reported_without_storage_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            config = ServiceConfig(
                output_file=str(base / "default.mp3"),
                webui_settings_path=base / "settings.json",
            )
            audio_cache, files, audio_dir = load_audio_files(config)
            server = MoonlightVoiceServer(("localhost", 0), config, audio_cache, files, audio_dir)
            try:
                reported = server.update_webui_settings(
                    {"tts_mode": "home_assistant", "output_format": "wav"}
                )
                self.assertEqual(reported["tts_mode"], "home_assistant")
                self.assertEqual(reported["output_format"], "wav")
                self.assertNotIn("webui_settings_path", reported)
                self.assertTrue(config.webui_settings_path.exists())
            finally:
                server.server_close()


class RequestDebugLoggingTest(unittest.TestCase):
    def test_debug_body_redacts_sensitive_json_fields(self) -> None:
        body = b'{"message":"Doorbell","api_key":"secret","nested":{"token":"hidden"}}'

        rendered = _format_debug_body(body, "application/json")

        self.assertIn('"message": "Doorbell"', rendered)
        self.assertNotIn("secret", rendered)
        self.assertNotIn("hidden", rendered)
        self.assertEqual(_format_debug_body(MP3_BYTES, "audio/mpeg"), "<10 bytes of binary data>")

    def test_tts_payload_description_identifies_supported_client_formats(self) -> None:
        self.assertEqual(
            _describe_tts_payload(urlparse("/tts"), b'{"message":"Doorbell"}'),
            "home_assistant:message",
        )
        self.assertEqual(
            _describe_tts_payload(urlparse("/tts"), b'{"input":"Doorbell"}'),
            "openai_compatible:input",
        )
        self.assertEqual(
            _describe_tts_payload(urlparse("/tts?text=Doorbell"), b""),
            "query:text",
        )


class TranscodeAudioTest(unittest.TestCase):
    def test_transcode_success_when_ffmpeg_outputs_file(self) -> None:
        def fake_run(cmd, **_kwargs):
            dest = Path(cmd[-1])
            dest.write_bytes(b"converted-data")
            return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

        with patch("moonlight_voice.server.subprocess.run", side_effect=fake_run):
            data, error = _transcode_audio(b"src", "mp3", "wav")
            self.assertEqual(data, b"converted-data")
            self.assertIsNone(error)

    def test_transcode_reports_ffmpeg_error(self) -> None:
        fake_proc = subprocess.CompletedProcess(
            args=["ffmpeg"], returncode=1, stdout=b"", stderr=b"boom"
        )
        with patch("moonlight_voice.server.subprocess.run", return_value=fake_proc):
            data, error = _transcode_audio(b"src", "mp3", "wav")
            self.assertIsNone(data)
            self.assertIn("ffmpeg exited with 1", error or "")
            self.assertIn("boom", error or "")

    def test_transcode_reports_missing_ffmpeg_binary(self) -> None:
        with patch("moonlight_voice.server.subprocess.run", side_effect=FileNotFoundError):
            data, error = _transcode_audio(b"src", "mp3", "wav")
            self.assertIsNone(data)
            self.assertIn("ffmpeg not available", error or "")


if __name__ == "__main__":
    unittest.main()
