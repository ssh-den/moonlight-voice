import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_ROOT = ROOT / "moonlight-voice"
ROOT_CHANGELOG_PATH = ROOT / "CHANGELOG.md"
ADDON_CHANGELOG_PATH = ADDON_ROOT / "CHANGELOG.md"
CONFIG_YAML_PATH = ADDON_ROOT / "config.yaml"
INTEGRATION_MANIFEST_PATH = ROOT / "custom_components" / "moonlight_voice" / "manifest.json"
HACS_MANIFEST_PATH = ROOT / "hacs.json"
BRAND_ICON_PATH = ROOT / "brand" / "icon.png"
INTEGRATION_ICON_PATH = INTEGRATION_MANIFEST_PATH.parent / "brand" / "icon.png"
ADDON_ICON_PATH = ADDON_ROOT / "icon.png"
SOURCE_ICON_PATH = ADDON_ROOT / "moonlight_voice/static/assets/icons/moon-star.svg"
WEBUI_DOM_PATH = ADDON_ROOT / "moonlight_voice/static/js/dom.js"

if str(ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDON_ROOT))

from moonlight_voice.config import SERVICE_VERSION


def _read_addon_version() -> str:
    for line in CONFIG_YAML_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("version:"):
            return stripped.split(":", 1)[1].strip()
    raise AssertionError("version not found in config.yaml")


def _read_changelog_version() -> str:
    first_release = next(
        line
        for line in ROOT_CHANGELOG_PATH.read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    )
    return first_release.removeprefix("## ").split(" ", 1)[0]


def _source_icon_paths() -> list[str]:
    return re.findall(r'<path d="([^"]+)" />', SOURCE_ICON_PATH.read_text(encoding="utf-8"))


def _webui_icon_paths() -> list[str]:
    dom = WEBUI_DOM_PATH.read_text(encoding="utf-8")
    match = re.search(r"const MOON_STAR_PATHS = \[(.*?)\];", dom, flags=re.DOTALL)
    if not match:
        raise AssertionError("MOON_STAR_PATHS not found in dom.js")
    return re.findall(r'"([^"]+)"', match[1])


class VersionConsistencyTest(unittest.TestCase):
    def test_webui_moon_star_paths_match_source_icon(self) -> None:
        self.assertEqual(_webui_icon_paths(), _source_icon_paths())

    def test_addon_and_service_versions_match(self) -> None:
        addon_version = _read_addon_version()

        self.assertEqual(addon_version, SERVICE_VERSION)

    def test_changelog_version_matches_service_version(self) -> None:
        self.assertEqual(_read_changelog_version(), SERVICE_VERSION)

    def test_github_and_addon_changelogs_are_identical(self) -> None:
        self.assertEqual(
            ROOT_CHANGELOG_PATH.read_text(encoding="utf-8"),
            ADDON_CHANGELOG_PATH.read_text(encoding="utf-8"),
        )

    def test_addon_manifest_enables_ingress_on_service_port(self) -> None:
        manifest = CONFIG_YAML_PATH.read_text(encoding="utf-8")
        self.assertIn("ingress: true", manifest)
        self.assertIn("ingress_port: 8031", manifest)

    def test_addon_manifest_advertises_the_custom_integration(self) -> None:
        manifest = CONFIG_YAML_PATH.read_text(encoding="utf-8")
        self.assertIn("discovery:\n  - moonlight_voice", manifest)

    def test_addon_manifest_leaves_tts_settings_to_webui(self) -> None:
        manifest = CONFIG_YAML_PATH.read_text(encoding="utf-8")
        self.assertNotIn("tts_mode:", manifest)
        self.assertNotIn("output_format:", manifest)

    def test_custom_integration_manifest_matches_addon_version(self) -> None:
        manifest = INTEGRATION_MANIFEST_PATH.read_text(encoding="utf-8")
        self.assertIn('"config_flow": true', manifest)
        self.assertIn(f'"version": "{SERVICE_VERSION}"', manifest)

    def test_custom_integration_has_hacs_metadata(self) -> None:
        manifest = json.loads(INTEGRATION_MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertTrue(
            {"domain", "documentation", "issue_tracker", "codeowners", "name", "version"}
            <= manifest.keys()
        )
        self.assertEqual(
            json.loads(HACS_MANIFEST_PATH.read_text(encoding="utf-8")),
            {"name": "Moonlight Voice"},
        )
        self.assertTrue(BRAND_ICON_PATH.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(BRAND_ICON_PATH.read_bytes(), ADDON_ICON_PATH.read_bytes())
        self.assertEqual(BRAND_ICON_PATH.read_bytes(), INTEGRATION_ICON_PATH.read_bytes())

    def test_custom_integration_uses_the_local_addon_hostname(self) -> None:
        constants = (ROOT / "custom_components" / "moonlight_voice" / "const.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('DEFAULT_URL = "http://local-moonlight-voice:8031"', constants)


if __name__ == "__main__":
    unittest.main()
