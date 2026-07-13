import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "moonlight-voice"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from moonlight_voice.config import DEFAULT_AUDIO_DIR, ServiceConfig


class ServiceConfigTest(unittest.TestCase):
    def test_defaults_and_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = ServiceConfig.load(options_path=Path(tmpdir) / "missing.json")
            cfg.normalize()
            self.assertEqual(cfg.output_format, "mp3")
            self.assertEqual(cfg.tts_mode, "openai_compatible")
            self.assertEqual(cfg.log_level, "info")
            self.assertEqual(cfg.resolved_audio_path().parent, DEFAULT_AUDIO_DIR)

    def test_loads_values(self) -> None:
        options = {
            "tts_mode": "home_assistant",
            "output_format": "wav",
            "output_file": "custom.wav",
            "log_level": "debug",
            "cache_headers": True,
            "port": 9999,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            options_path = Path(tmpdir) / "options.json"
            options_path.write_text(json.dumps(options), encoding="utf-8")

            cfg = ServiceConfig.load(
                options_path=options_path,
                webui_settings_path=Path(tmpdir) / "settings.json",
            )
            cfg.normalize()

            self.assertEqual(cfg.output_format, "wav")
            self.assertEqual(cfg.tts_mode, "home_assistant")
            self.assertEqual(cfg.output_file, "custom.wav")
            self.assertEqual(cfg.log_level, "debug")
            self.assertTrue(cfg.cache_headers)
            self.assertEqual(cfg.port, 9999)
            self.assertEqual(cfg.resolved_audio_path(), DEFAULT_AUDIO_DIR / "custom.wav")

    def test_normalizes_upload_limit(self) -> None:
        cfg = ServiceConfig(max_upload_size_mb=0)
        cfg.normalize()
        self.assertEqual(cfg.max_upload_size_mb, 1)
        self.assertEqual(cfg.max_upload_bytes, 1024 * 1024)

    def test_normalizes_unknown_tts_mode(self) -> None:
        cfg = ServiceConfig(tts_mode="unsupported")
        cfg.normalize()
        self.assertEqual(cfg.tts_mode, "openai_compatible")

    def test_webui_settings_override_addon_options_and_persist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            options_path = base / "options.json"
            settings_path = base / "settings.json"
            options_path.write_text(
                json.dumps({"tts_mode": "home_assistant", "output_format": "wav"}),
                encoding="utf-8",
            )
            settings_path.write_text(
                json.dumps({"tts_mode": "openai_compatible", "output_format": "mp3"}),
                encoding="utf-8",
            )

            cfg = ServiceConfig.load(options_path, settings_path)
            self.assertEqual(cfg.tts_mode, "openai_compatible")
            self.assertEqual(cfg.output_format, "mp3")

            cfg.update_webui_settings({"tts_mode": "home_assistant", "output_format": "wav"})
            restored = ServiceConfig.load(options_path, settings_path)
            self.assertEqual(restored.tts_mode, "home_assistant")
            self.assertEqual(restored.output_format, "wav")


if __name__ == "__main__":
    unittest.main()
