import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "moonlight-voice"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from moonlight_voice.web import get_static_dir, load_index_html, load_static_asset


class StaticAssetsTest(unittest.TestCase):
    def test_index_loads_from_disk(self) -> None:
        body, content_type = load_index_html(get_static_dir())
        self.assertIn(b"Moonlight Voice", body)
        self.assertEqual(content_type, "text/html; charset=utf-8")

    def test_ui_uses_relative_urls_for_home_assistant_ingress(self) -> None:
        index, _ = load_index_html(get_static_dir())
        app, _ = load_static_asset("js/api.js", get_static_dir())
        self.assertIn(b'href="static/css/tokens.css"', index)
        self.assertIn(b'src="static/js/app.js"', index)
        self.assertIn(b"const endpoint = (path)", app)
        self.assertNotIn(b"fetch('/", app)

    def test_stylesheet_exposes_design_tokens(self) -> None:
        css, content_type = load_static_asset("css/tokens.css", get_static_dir())
        self.assertIn(b":root", css)
        self.assertIn(b"--color-primary", css)
        self.assertIn(b"--color-background", css)
        self.assertEqual(content_type, "text/css; charset=utf-8")

    def test_ui_uses_modular_assets_and_accessible_tabs(self) -> None:
        index, _ = load_index_html(get_static_dir())
        for asset in (
            "js/app.js",
            "js/api.js",
            "js/state.js",
            "js/dom.js",
            "js/tabs.js",
            "js/features/audio-library.js",
            "js/features/service-overview.js",
            "js/features/endpoint-settings.js",
        ):
            body, _ = load_static_asset(asset, get_static_dir())
            self.assertTrue(body, asset)
        self.assertIn(b'role="tablist"', index)
        self.assertIn(b'role="tabpanel"', index)

    def test_ui_uses_individual_icon_assets_and_file_picker_behavior(self) -> None:
        index, _ = load_index_html(get_static_dir())
        css, _ = load_static_asset("css/components.css", get_static_dir())
        dom, _ = load_static_asset("js/dom.js", get_static_dir())
        audio_library, _ = load_static_asset("js/features/audio-library.js", get_static_dir())
        for icon in (
            "edit",
            "file-audio",
            "moon-star",
            "play",
            "search",
            "trash",
            "upload",
        ):
            asset, content_type = load_static_asset(f"assets/icons/{icon}.svg", get_static_dir())
            self.assertIn(b"<svg", asset)
            self.assertEqual(content_type, "image/svg+xml")
        self.assertIn(b"shape-rendering: geometricPrecision", css)
        self.assertIn(b"ICON_SHAPES", dom)
        self.assertIn(b"moon-star-gradient", dom)
        self.assertIn(b"createElementNS", dom)
        self.assertIn(b'data-icon="upload"', index)
        self.assertIn(b"data-file-picker", index)
        self.assertIn(b"dragover", dom)
        self.assertIn(b"dataTransfer", dom)
        self.assertIn(b"default-file-info", index)
        self.assertIn(b"default_file_details", audio_library)
        self.assertIn(b'"Delete response"', audio_library)
        self.assertIn(b'`Delete response "${code}"? This cannot be undone.`', audio_library)
        self.assertIn(b"await api.deleteResponse(code)", audio_library)
        self.assertIn(b"createNotice({ dismissAfterMs = 0 } = {})", dom)
        self.assertIn(b"if (dismissAfterMs > 0)", dom)
        self.assertIn(b'id="tts-settings-form"', index)
        self.assertIn(b"updateConfig", load_static_asset("js/api.js", get_static_dir())[0])

    def test_index_is_composed_from_readable_components(self) -> None:
        index, _ = load_index_html(get_static_dir())
        template, _ = load_static_asset("index.html", get_static_dir())
        self.assertIn(b"<!-- include: audio-library.html -->", template)
        self.assertIn(b'id="panel-audio-library"', index)
        self.assertNotIn(b"<!-- include:", index)

    def test_traversal_attempt_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            load_static_asset("../config.yaml", get_static_dir())


if __name__ == "__main__":
    unittest.main()
